import re
from core.utils.nl_to_sparql import nl_to_sparql, nl_to_sparql_update
from core.utils.fuseki import sparql_query, sparql_update
from .ontology_manager import create_schedule, list_schedules, update_schedule, delete_schedule


def is_update_query(sparql_text: str) -> bool:
    txt = (sparql_text or "").strip().upper()
    return any(k in txt for k in ["INSERT", "DELETE", "WITH", "DELETE DATA", "INSERT DATA"]) and "SELECT" not in txt


def detect_intent(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\b(delete|remove|supprimer|effacer|drop)\b", t):
        return "delete"
    if re.search(r"\b(update|modify|change|edit|mettre\s+à\s+jour|changer)\b", t):
        return "update"
    if re.search(r"\b(create|add|insert|ajouter|créer)\b", t):
        return "create"
    return "read"


def ai_generate_and_execute(nl_text: str):
    if not nl_text or not nl_text.strip():
        return {"error": "Empty query"}
    intent = detect_intent(nl_text)
    if intent == 'create':
        try:
            payload = infer_create_payload(nl_text)
            sid = create_schedule(payload)
            return {"ok": True, "mode": "create", "created_id": sid}
        except Exception as e:
            # fallback
            u = nl_to_sparql_update(nl_text)
            if not u:
                return {"error": f"Create failed: {e}"}
            try:
                sparql_update(u)
                return {"ok": True, "mode": "update", "sparql": u}
            except Exception as e2:
                return {"error": f"Create failed: {e}; Update fallback failed: {e2}"}

    if intent == 'delete':
        sid = _extract_id(nl_text)
        if sid:
            try:
                ok = delete_schedule(sid)
                if ok:
                    return {"ok": True, "mode": "update", "deleted_id": sid}
            except Exception as e:
                # fallback if canonical delete fails
                pass
        # fallback to AI SPARQL
        u = nl_to_sparql_update(nl_text)
        if not u:
            return {"error": "AI failed to generate DELETE"}
        try:
            sparql_update(u)
            return {"ok": True, "mode": "update", "sparql": u}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": u}

    if intent == 'update':
        sid = _extract_id(nl_text)
        if sid:
            try:
                # Build partial data from NL
                data = infer_update_payload(nl_text)
                if data:
                    update_schedule(sid, data)
                    return {"ok": True, "mode": "update", "updated_id": sid, "data": data}
            except Exception:
                pass
        # fallback to AI SPARQL
        u = nl_to_sparql_update(nl_text)
        if not u:
            return {"error": "AI failed to generate UPDATE SPARQL"}
        try:
            sparql_update(u)
            return {"ok": True, "mode": "update", "sparql": u}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": u}

    # read
    s = nl_to_sparql(nl_text)
    if not s:
        return {"error": "AI failed to generate SPARQL"}
    if is_update_query(s):
        try:
            sparql_update(s)
            return {"ok": True, "mode": "update", "sparql": s}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": s}
    try:
        res = sparql_query(s)
        return {"ok": True, "mode": "select", "sparql": s, "results": res}
    except Exception as e:
        return {"error": str(e), "mode": "select", "sparql": s}


def infer_create_payload(text: str):
    t = (text or '').lower()
    # detect type for ID prefix
    if re.search(r"\b(daily|journalier|quotidien)\b", t):
        sch_type = 'Daily'
        prefix = 'S-D-'
    elif re.search(r"\b(seasonal|saisonnier|season)\b", t):
        sch_type = 'Seasonal'
        prefix = 'S-S-'
    elif re.search(r"\b(on\s*demand|à\s*la\s*demande)\b", t):
        sch_type = 'OnDemand'
        prefix = 'S-O-'
    else:
        sch_type = ''
        prefix = 'S-'

    # next numeric from existing for the chosen prefix
    next_numeric = _next_numeric(prefix)
    data = {
        'schedule_id': str(next_numeric),
        'schedule_type': sch_type,
        'route_name': _extract_text(t, r"route\s*(?:name)?\s*(?:is|=|:)?\s*([\w\-\s]{2,})"),
        'effective_date': _extract_text(t, r"(date|effective)\s*(?:is|=|:)?\s*([\w\-/:]+)"),
        'is_public': bool(re.search(r"\b(public|publique)\b", t)),
    }
    return data


def _next_numeric(prefix: str):
    rows = list_schedules() or []
    max_num = -1
    for r in rows:
        rid = (r.get('id') or '').upper()
        if rid.startswith(prefix.upper()):
            try:
                num = int(rid.split('-')[-1])
                if num > max_num:
                    max_num = num
            except Exception:
                continue
    return (max_num + 1) if max_num >= 0 else 1


def _extract_text(t: str, pattern: str):
    m = re.search(pattern, t)
    if not m:
        return ''
    return (m.group(1) if m.lastindex == 1 else m.group(2)).strip()


def _extract_id(text: str) -> str:
    t = (text or '').strip()
    # Match S-*-NNN or SCH-NNN
    m = re.search(r"\b(S-(?:[A-Z]-)?\d{3}|SCH-\d{3})\b", t, flags=re.IGNORECASE)
    return m.group(1).upper() if m else ''


def infer_update_payload(text: str):
    t = (text or '').lower()
    data = {}
    # detect type to allow adding type-specific fields
    if re.search(r"\b(daily|journalier|quotidien)\b", t):
        data['schedule_type'] = 'Daily'
    elif re.search(r"\b(seasonal|saisonnier|season)\b", t):
        data['schedule_type'] = 'Seasonal'
    elif re.search(r"\b(on\s*demand|à\s*la\s*demande)\b", t):
        data['schedule_type'] = 'OnDemand'

    # common fields
    rn = _extract_text(t, r"route\s*(?:name)?\s*(?:to|=|:)\s*([\w\-\s]{2,})")
    if rn: data['route_name'] = rn
    eff = _extract_text(t, r"(effective\s*date|date)\s*(?:to|=|:)\s*([\w\-/:]+)")
    if eff: data['effective_date'] = eff
    if re.search(r"\b(public|publique)\b", t):
        data['is_public'] = True
    if re.search(r"\b(private|non\s*public)\b", t):
        data['is_public'] = False

    # daily
    fr = _extract_text(t, r"first\s*run\s*time\s*(?:to|=|:)\s*([\d:]{4,5})")
    if fr: data['first_run_time'] = fr
    lr = _extract_text(t, r"last\s*run\s*time\s*(?:to|=|:)\s*([\d:]{4,5})")
    if lr: data['last_run_time'] = lr
    fm = _extract_text(t, r"frequency\s*(?:minutes|mins)?\s*(?:to|=|:)\s*(\d+)")
    if fm: data['frequency_minutes'] = int(fm)
    mask = _extract_text(t, r"day\s*of\s*week\s*mask\s*(?:to|=|:)\s*([\w\-]+)")
    if mask: data['day_of_week_mask'] = mask

    # seasonal
    season = _extract_text(t, r"season\s*(?:to|=|:)\s*([\w\-]+)")
    if season: data['season'] = season
    sd = _extract_text(t, r"start\s*date\s*(?:to|=|:)\s*([\w\-/:]+)")
    if sd: data['start_date'] = sd
    ed = _extract_text(t, r"end\s*date\s*(?:to|=|:)\s*([\w\-/:]+)")
    if ed: data['end_date'] = ed
    ocp = _extract_text(t, r"operational\s*capacity\s*(?:%|percent|percentage)\s*(?:to|=|:)\s*(\d+)")
    if ocp: data['operational_capacity_percentage'] = int(ocp)

    # on-demand
    bl = _extract_text(t, r"booking\s*lead\s*time\s*(?:hours|h)?\s*(?:to|=|:)\s*(\d+)")
    if bl: data['booking_lead_time_hours'] = int(bl)
    sws = _extract_text(t, r"service\s*window\s*start\s*(?:to|=|:)\s*([\d:]{4,5})")
    if sws: data['service_window_start'] = sws
    swe = _extract_text(t, r"service\s*window\s*end\s*(?:to|=|:)\s*([\d:]{4,5})")
    if swe: data['service_window_end'] = swe
    mw = _extract_text(t, r"max\s*wait\s*time\s*(?:minutes|mins)?\s*(?:to|=|:)\s*(\d+)")
    if mw: data['max_wait_time_minutes'] = int(mw)

    return data


