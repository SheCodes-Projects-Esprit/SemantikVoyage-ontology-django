import time
import traceback
from django.conf import settings
from core.utils.fuseki import sparql_query, sparql_update
import requests
from urllib.parse import urlencode

NS = "http://www.transport-ontology.org/travel#"

# Reuse rdflib store from itinerary
USE_RDFLIB = True
try:
    from rdflib import Namespace, URIRef, Literal
    from rdflib.namespace import RDF, XSD
    from itinerary.utils.rdflib_store import get_graph, get_named_graph
    TR = Namespace(NS)
except Exception:
    USE_RDFLIB = False


def _run_sparql(query, expect_json=True, timeout=10, all_graphs=False):
    try:
        FUSEKI_QUERY_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/query"
    except Exception:
        FUSEKI_QUERY_URL = "http://localhost:3030/transport_db/query"

    if all_graphs:
        try:
            headers = {'Accept': 'application/sparql-results+json'}
            resp = requests.get(FUSEKI_QUERY_URL, params={'query': query, 'unionDefaultGraph': 'true'}, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"_run_sparql (all_graphs) failed: {e}")
            return {}
    try:
        res = sparql_query(query)
        if isinstance(res, dict) and (res.get('results', {}).get('bindings') or 'boolean' in res):
            return res
    except Exception as e:
        print(f"_run_sparql wrapper failed: {e}")
    try:
        headers = {'Accept': 'application/sparql-results+json'}
        resp = requests.get(FUSEKI_QUERY_URL, params={'query': query, 'unionDefaultGraph': 'true'}, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def normalize_schedule_id(schedule_id):
    if isinstance(schedule_id, int):
        return f"{schedule_id:03d}"
    try:
        s = str(schedule_id).strip()
        if '-' in s:
            parts = s.split('-')
            if len(parts) >= 2:
                # keep first two parts as prefix when available (e.g., S-D)
                if len(parts) >= 3:
                    prefix = f"{parts[0]}-{parts[1]}"
                    num = parts[2].lstrip('0') or '0'
                    return f"{prefix}-{int(num):03d}"
                else:
                    prefix = parts[0]
                    num = parts[1].lstrip('0') or '0'
                    return f"{prefix}-{int(num):03d}"
        return f"{int(s):03d}"
    except Exception:
        return "000"


def create_schedule(data):
    if USE_RDFLIB:
        return _create_schedule_rdflib(data)
    # SPARQL fallback
    sid = str(data.get('schedule_id', '0')).strip()
    try:
        normalized = f"{int(sid):03d}"
    except Exception:
        normalized = "000"
    sch_type = data.get('schedule_type') or ''
    # ID prefix mapping to match ontology: S-D-xxx (Daily), S-S-xxx (Seasonal), S-O-xxx (OnDemand)
    if sch_type == 'Daily':
        prefix = 'S-D-'
    elif sch_type == 'Seasonal':
        prefix = 'S-S-'
    elif sch_type == 'OnDemand':
        prefix = 'S-O-'
    else:
        prefix = 'S-'
    full_id = f"{prefix}{normalized}"
    uri = f":{full_id}"
    sch_type = data.get('schedule_type') or ''
    rdf_type = ':Schedule'
    if sch_type == 'Daily':
        rdf_type = ':DailySchedule'
    elif sch_type == 'Seasonal':
        rdf_type = ':SeasonalSchedule'
    elif sch_type == 'OnDemand':
        rdf_type = ':OnDemandSchedule'

    triples = [
        f"{uri} a {rdf_type} .",
        f'{uri} :scheduleID "{full_id}" .',
    ]
    if data.get('route_name'):
        triples.append(f'{uri} :routeName "{data["route_name"]}" .')
    if data.get('effective_date'):
        triples.append(f'{uri} :effectiveDate "{data["effective_date"]}" .')
    triples.append(f'{uri} :isPublic {str(bool(data.get("is_public", False))).lower()} .')
    # Type-specific
    if sch_type == 'Daily':
        if data.get('first_run_time'):
            triples.append(f'{uri} :firstRunTime "{data["first_run_time"]}" .')
        if data.get('last_run_time'):
            triples.append(f'{uri} :lastRunTime "{data["last_run_time"]}" .')
        if data.get('frequency_minutes') is not None and data.get('frequency_minutes') != '':
            try:
                fm = int(data['frequency_minutes'])
                triples.append(f'{uri} :frequencyMinutes {fm} .')
            except Exception:
                pass
        if data.get('day_of_week_mask'):
            triples.append(f'{uri} :dayOfWeekMask "{data["day_of_week_mask"]}" .')
    elif sch_type == 'Seasonal':
        if data.get('season'):
            triples.append(f'{uri} :season "{data["season"]}" .')
        if data.get('start_date'):
            triples.append(f'{uri} :startDate "{data["start_date"]}" .')
        if data.get('end_date'):
            triples.append(f'{uri} :endDate "{data["end_date"]}" .')
        if data.get('operational_capacity_percentage') is not None and data.get('operational_capacity_percentage') != '':
            try:
                ocp = int(data['operational_capacity_percentage'])
                triples.append(f'{uri} :operationalCapacityPercentage {ocp} .')
            except Exception:
                pass
    elif sch_type == 'OnDemand':
        if data.get('booking_lead_time_hours') is not None and data.get('booking_lead_time_hours') != '':
            try:
                bl = int(data['booking_lead_time_hours'])
                triples.append(f'{uri} :bookingLeadTimeHours {bl} .')
            except Exception:
                pass
        if data.get('service_window_start'):
            triples.append(f'{uri} :serviceWindowStart "{data["service_window_start"]}" .')
        if data.get('service_window_end'):
            triples.append(f'{uri} :serviceWindowEnd "{data["service_window_end"]}" .')
        if data.get('max_wait_time_minutes') is not None and data.get('max_wait_time_minutes') != '':
            try:
                mw = int(data['max_wait_time_minutes'])
                triples.append(f'{uri} :maxWaitTimeMinutes {mw} .')
            except Exception:
                pass
    triples_str = "\n      ".join(triples)
    sparql = f"""
    PREFIX : <{NS}>
    INSERT DATA {{
      {triples_str}
    }}
    """
    sparql_update(sparql)
    return full_id


def _create_schedule_rdflib(data):
    sid = str(data.get('schedule_id', '0')).strip()
    try:
        normalized = f"{int(sid):03d}"
    except Exception:
        normalized = "000"
    sch_type = data.get('schedule_type') or ''
    if sch_type == 'Daily':
        prefix = 'S-D-'
    elif sch_type == 'Seasonal':
        prefix = 'S-S-'
    elif sch_type == 'OnDemand':
        prefix = 'S-O-'
    else:
        prefix = 'S-'
    full_id = f"{prefix}{normalized}"
    subj = URIRef(f"{NS}{full_id}")
    g = get_graph(); ctx = get_named_graph(g)
    sch_type = data.get('schedule_type') or ''
    if sch_type == 'Daily':
        ctx.add((subj, RDF.type, TR.DailySchedule))
    elif sch_type == 'Seasonal':
        ctx.add((subj, RDF.type, TR.SeasonalSchedule))
    elif sch_type == 'OnDemand':
        ctx.add((subj, RDF.type, TR.OnDemandSchedule))
    else:
        ctx.add((subj, RDF.type, TR.Schedule))
    ctx.add((subj, TR.scheduleID, Literal(full_id)))
    if data.get('route_name'):
        ctx.add((subj, TR.routeName, Literal(str(data['route_name']))))
    if data.get('effective_date'):
        ctx.add((subj, TR.effectiveDate, Literal(str(data['effective_date']))))
    ctx.add((subj, TR.isPublic, Literal(bool(data.get('is_public', False)))))
    # Type-specific
    if sch_type == 'Daily':
        if data.get('first_run_time'):
            ctx.add((subj, TR.firstRunTime, Literal(str(data['first_run_time']))))
        if data.get('last_run_time'):
            ctx.add((subj, TR.lastRunTime, Literal(str(data['last_run_time']))))
        if data.get('frequency_minutes') not in (None, ''):
            try:
                ctx.add((subj, TR.frequencyMinutes, Literal(int(data['frequency_minutes']))))
            except Exception:
                pass
        if data.get('day_of_week_mask'):
            ctx.add((subj, TR.dayOfWeekMask, Literal(str(data['day_of_week_mask']))))
    elif sch_type == 'Seasonal':
        if data.get('season'):
            ctx.add((subj, TR.season, Literal(str(data['season']))))
        if data.get('start_date'):
            ctx.add((subj, TR.startDate, Literal(str(data['start_date']))))
        if data.get('end_date'):
            ctx.add((subj, TR.endDate, Literal(str(data['end_date']))))
        if data.get('operational_capacity_percentage') not in (None, ''):
            try:
                ctx.add((subj, TR.operationalCapacityPercentage, Literal(int(data['operational_capacity_percentage']))))
            except Exception:
                pass
    elif sch_type == 'OnDemand':
        if data.get('booking_lead_time_hours') not in (None, ''):
            try:
                ctx.add((subj, TR.bookingLeadTimeHours, Literal(int(data['booking_lead_time_hours']))))
            except Exception:
                pass
        if data.get('service_window_start'):
            ctx.add((subj, TR.serviceWindowStart, Literal(str(data['service_window_start']))))
        if data.get('service_window_end'):
            ctx.add((subj, TR.serviceWindowEnd, Literal(str(data['service_window_end']))))
        if data.get('max_wait_time_minutes') not in (None, ''):
            try:
                ctx.add((subj, TR.maxWaitTimeMinutes, Literal(int(data['max_wait_time_minutes']))))
            except Exception:
                pass
    return full_id


def get_schedule(sid, subject_uri=None):
    sid = str(sid).strip()
    candidates = [sid] if sid.startswith('SCH-') else [f"SCH-{normalize_schedule_id(sid)}"]
    if subject_uri:
        nodes = [f"<{subject_uri}>"]
    else:
        nodes = [f":{c}" for c in candidates] + [f"<{NS}{c}>" for c in candidates]
    for node in nodes:
        q = f"""
        PREFIX : <{NS}>
        SELECT ?p ?o WHERE {{ {node} ?p ?o }}
        """
        res = _run_sparql(q)
        bindings = res.get('results', {}).get('bindings', []) if isinstance(res, dict) else []
        if bindings:
            data = {}
            for b in bindings:
                p = b.get('p', {}).get('value', '')
                o = b.get('o', {}).get('value', '')
                data[p.split('#')[-1]] = o
            data['id'] = data.get('scheduleID', candidates[0])
            return data
    return None


def update_schedule(sid, new_data, subject_uri=None):
    existing = get_schedule(sid, subject_uri)
    if not existing:
        return create_schedule(new_data)
    full_id = existing.get('scheduleID', sid)
    nodes = [f":{full_id}", f"<{NS}{full_id}>"]
    if subject_uri:
        nodes.insert(0, f"<{subject_uri}>")
    for n in nodes:
        sparql_update(f"PREFIX : <{NS}> DELETE WHERE {{ {n} ?p ?o }}")
        sparql_update(f"PREFIX : <{NS}> DELETE WHERE {{ ?s ?p {n} }}")
    new_data['schedule_id'] = full_id.split('-')[-1]
    return create_schedule(new_data)


def delete_schedule(sid, subject_uri=None):
    existing = get_schedule(sid, subject_uri)
    # Accept new prefixed IDs (S-D-xxx etc.) as well as legacy SCH-xxx
    if existing:
        full_id = existing.get('scheduleID', sid) or existing.get('id', sid)
    else:
        nid = normalize_schedule_id(sid)
        # If the incoming id already looks like S-*-NNN keep as-is; else fallback SCH-
        full_id = sid if sid.upper().startswith('S-') else f"SCH-{nid}"

    nodes = [f":{full_id}", f"<{NS}{full_id}>"]
    if subject_uri:
        nodes.insert(0, f"<{subject_uri}>")
    ok = True
    graph_uri = getattr(settings, 'FUSEKI_GRAPH', None)
    for n in nodes:
        try:
            sparql_update(f"PREFIX : <{NS}> DELETE WHERE {{ {n} ?p ?o }}")
            sparql_update(f"PREFIX : <{NS}> DELETE WHERE {{ ?s ?p {n} }}")
        except Exception:
            ok = False
        # Also delete inside configured named graph
        if graph_uri:
            try:
                sparql_update(f"PREFIX : <{NS}> DELETE WHERE {{ GRAPH <{graph_uri}> {{ {n} ?p ?o }} }}")
                sparql_update(f"PREFIX : <{NS}> DELETE WHERE {{ GRAPH <{graph_uri}> {{ ?s ?p {n} }} }}")
            except Exception:
                ok = False
    return ok


def list_schedules(filters=None):
    filters = filters or {}
    all_bindings = []
    seen_subjects = set()

    # Query 1: search without GRAPH restriction (union default graph)
    q1 = f"""
    PREFIX : <{NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?s ?id ?type ?route ?date ?pub WHERE {{
      {{ ?s rdf:type/rdfs:subClassOf* :Schedule . OPTIONAL {{ ?s :scheduleID ?id }} }}
      UNION
      {{ ?s :scheduleID ?id . OPTIONAL {{ ?s rdf:type/rdfs:subClassOf* :Schedule }} }}
      OPTIONAL {{ ?s rdf:type ?type }}
      OPTIONAL {{ ?s :routeName ?route }}
      OPTIONAL {{ ?s :effectiveDate ?date }}
      OPTIONAL {{ ?s :isPublic ?pub }}
    }}
    ORDER BY ?id
    LIMIT 500
    """
    r1 = _run_sparql(q1, all_graphs=True)
    b1 = r1.get('results', {}).get('bindings', []) if isinstance(r1, dict) else []
    for b in b1:
        s_uri = b.get('s', {}).get('value', '') if isinstance(b.get('s'), dict) else ''
        if s_uri and s_uri not in seen_subjects:
            all_bindings.append(b); seen_subjects.add(s_uri)

    # Query 2: explicit named graph if configured
    try:
        graph_uri = getattr(settings, 'FUSEKI_GRAPH', None)
        if graph_uri:
            q2 = f"""
            PREFIX : <{NS}>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?s ?id ?type ?route ?date ?pub WHERE {{
              GRAPH <{graph_uri}> {{
                {{ ?s rdf:type/rdfs:subClassOf* :Schedule . OPTIONAL {{ ?s :scheduleID ?id }} }}
                UNION
                {{ ?s :scheduleID ?id . OPTIONAL {{ ?s rdf:type/rdfs:subClassOf* :Schedule }} }}
                OPTIONAL {{ ?s rdf:type ?type }}
                OPTIONAL {{ ?s :routeName ?route }}
                OPTIONAL {{ ?s :effectiveDate ?date }}
                OPTIONAL {{ ?s :isPublic ?pub }}
              }}
            }}
            ORDER BY ?id
            LIMIT 500
            """
            r2 = _run_sparql(q2, all_graphs=True)
            b2 = r2.get('results', {}).get('bindings', []) if isinstance(r2, dict) else []
            for b in b2:
                s_uri = b.get('s', {}).get('value', '') if isinstance(b.get('s'), dict) else ''
                if s_uri and s_uri not in seen_subjects:
                    all_bindings.append(b); seen_subjects.add(s_uri)
    except Exception:
        pass

    # Query 3: scan across all named graphs
    q3 = f"""
    PREFIX : <{NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?g ?s ?id ?type ?route ?date ?pub WHERE {{
      GRAPH ?g {{
        {{ ?s rdf:type/rdfs:subClassOf* :Schedule . OPTIONAL {{ ?s :scheduleID ?id }} }}
        UNION
        {{ ?s :scheduleID ?id . OPTIONAL {{ ?s rdf:type/rdfs:subClassOf* :Schedule }} }}
        OPTIONAL {{ ?s rdf:type ?type }}
        OPTIONAL {{ ?s :routeName ?route }}
        OPTIONAL {{ ?s :effectiveDate ?date }}
        OPTIONAL {{ ?s :isPublic ?pub }}
      }}
    }}
    ORDER BY ?id
    LIMIT 500
    """
    r3 = _run_sparql(q3, all_graphs=True)
    b3 = r3.get('results', {}).get('bindings', []) if isinstance(r3, dict) else []
    for b in b3:
        s_uri = b.get('s', {}).get('value', '') if isinstance(b.get('s'), dict) else ''
        if s_uri and s_uri not in seen_subjects:
            all_bindings.append(b); seen_subjects.add(s_uri)

    rows = []
    seen_ids = set()
    for b in all_bindings:
        iid_obj = b.get('id', {})
        iid = iid_obj.get('value', '') if isinstance(iid_obj, dict) else str(iid_obj) if iid_obj else ''
        if not iid:
            s_obj = b.get('s', {})
            s_uri = s_obj.get('value', '') if isinstance(s_obj, dict) else str(s_obj) if s_obj else ''
            if s_uri:
                local = s_uri.split('#')[-1] if '#' in s_uri else s_uri.split('/')[-1]
                if '/' in local:
                    local = local.split('/')[-1]
                iid = local
        if not iid or iid in seen_ids:
            continue
        seen_ids.add(iid)

        type_val_obj = b.get('type', {})
        type_val = type_val_obj.get('value', '') if isinstance(type_val_obj, dict) else str(type_val_obj) if type_val_obj else ''
        if 'DailySchedule' in type_val:
            tname = 'Daily'
        elif 'SeasonalSchedule' in type_val:
            tname = 'Seasonal'
        elif 'OnDemandSchedule' in type_val:
            tname = 'OnDemand'
        elif 'Schedule' in type_val:
            tname = 'Schedule'
        else:
            tname = 'Schedule'

        row = {
            'id': iid,
            'type': tname,
            'route': (b.get('route', {}) or {}).get('value', ''),
            'date': (b.get('date', {}) or {}).get('value', ''),
            'public': (b.get('pub', {}) or {}).get('value', ''),
            'subject': (b.get('s', {}) or {}).get('value', ''),
        }

        # Filters support
        if filters.get('id_in'):
            allowed = {i.strip() for i in str(filters['id_in']).split(',') if i.strip()}
            if row['id'] not in allowed:
                continue
        if filters.get('type') and filters['type'].strip().title() != row['type']:
            continue

        rows.append(row)

    rows.sort(key=lambda x: x['id'])
    return rows


