import re
from core.utils.nl_to_sparql import nl_to_sparql, nl_to_sparql_update
from core.utils.fuseki import sparql_query, sparql_update
from .ontology_manager import create_itinerary, list_itineraries


def is_update_query(sparql_text: str) -> bool:
    txt = (sparql_text or "").strip().upper()
    return any(k in txt for k in ["INSERT", "DELETE", "WITH", "DELETE DATA", "INSERT DATA"]) and "SELECT" not in txt


def ai_generate_and_execute(nl_text: str):
    """
    Convert natural language to SPARQL via AI, auto-detect SELECT vs UPDATE,
    execute against Fuseki, and return a uniform response dict.
    """
    if not nl_text or not nl_text.strip():
        return {"error": "Empty query"}

    # Try to generate SELECT first; if it looks like update intent, generate update instead
    # Heuristic: look for CR(U)D verbs
    intent = detect_intent(nl_text)

    if intent in {"create", "update", "delete"}:
        # Special handling: for CREATE, use our canonical create_itinerary logic (same as manual creation)
        if intent == "create":
            try:
                payload = infer_create_payload(nl_text)
                new_id = create_itinerary(payload["data"], payload["type"])  # returns full_id like I-B-0NN
                return {"ok": True, "mode": "create", "created_id": new_id, "data": payload["data"]}
            except Exception as e:
                # Fallback: try raw UPDATE if canonical creation failed
                sparql_fb = nl_to_sparql_update(nl_text)
                if not sparql_fb:
                    return {"error": f"Create failed: {e}"}
                try:
                    sparql_update(sparql_fb)
                    return {"ok": True, "mode": "update", "sparql": sparql_fb}
                except Exception as e2:
                    return {"error": f"Create failed: {e}; Update fallback failed: {e2}"}

        # For UPDATE/DELETE, keep AI SPARQL behavior
        sparql = nl_to_sparql_update(nl_text)
        if not sparql:
            return {"error": "AI failed to generate UPDATE SPARQL"}
        try:
            sparql_update(sparql)
            return {"ok": True, "mode": "update", "sparql": sparql}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": sparql}

    # Read/list default
    sparql = nl_to_sparql(nl_text)
    if not sparql:
        return {"error": "AI failed to generate SPARQL"}

    # If AI accidentally returned an update, route accordingly
    if is_update_query(sparql):
        try:
            sparql_update(sparql)
            return {"ok": True, "mode": "update", "sparql": sparql}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": sparql}

    try:
        res = sparql_query(sparql)
        return {"ok": True, "mode": "select", "sparql": sparql, "results": res}
    except Exception as e:
        return {"error": str(e), "mode": "select", "sparql": sparql}


def detect_intent(text: str) -> str:
    t = (text or "").lower()
    # Delete
    if re.search(r"\b(delete|remove|supprimer|effacer|drop)\b", t):
        return "delete"
    # Update
    if re.search(r"\b(update|modify|change|edit|mettre\s+à\s+jour|changer)\b", t):
        return "update"
    # Create
    if re.search(r"\b(create|add|insert|ajouter|créer)\b", t):
        return "create"
    # Read
    return "read"


# ------------------------------
# Create inference helpers
# ------------------------------

def infer_create_payload(text: str):
    t = (text or "").lower()
    # Determine type
    if re.search(r"\b(business|affaire|entreprise)\b", t):
        it_type = "Business"
        prefix = "I-B-"
    elif re.search(r"\b(leisure|loisir|vacances)\b", t):
        it_type = "Leisure"
        prefix = "I-L-"
    elif re.search(r"\b(educational|education|study|formation|cours|université)\b", t):
        it_type = "Educational"
        prefix = "I-E-"
    else:
        # default to Business if not specified
        it_type = "Business"
        prefix = "I-B-"

    # Extract optional numbers
    cost_match = re.search(r"(cost|budget|price|coût|budget)\s*(?:is|=|:)?\s*([0-9]+(?:\.[0-9]+)?)", t)
    days_match = re.search(r"(day|days|jour|jours)\s*([0-9]+)", t)
    status_match = re.search(r"\b(completed|in\s*progress|planned|cancelled)\b", t)

    # Build next ID
    next_numeric = _next_numeric_for_prefix(prefix)

    data = {
        "itinerary_id": str(next_numeric),
        "overall_status": (status_match.group(1).replace(" ", "") if status_match else "Planned").title().replace(" ", ""),
        "total_cost_estimate": float(cost_match.group(2)) if cost_match else 0.0,
        "total_duration_days": int(days_match.group(2)) if days_match else 1,
    }

    return {"type": it_type, "data": data}


def _next_numeric_for_prefix(prefix: str) -> int:
    rows = list_itineraries() or []
    max_num = -1
    for r in rows:
        rid = (r.get("id") or "").upper()
        if rid.startswith(prefix.upper()):
            try:
                num = int(rid.split('-')[-1])
                if num > max_num:
                    max_num = num
            except Exception:
                continue
    return (max_num + 1) if max_num >= 0 else 1


