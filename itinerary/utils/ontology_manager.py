# itinerary/utils/ontology_manager.py - FIXED WITH CORRECT URI PATTERN
import time
import traceback
from django.conf import settings
from core.utils.fuseki import sparql_query, sparql_update
import requests
from urllib.parse import urlencode


# ----------------------------------------------------------------------
# CONFIGURATION FUSEKI
# ----------------------------------------------------------------------
try:
    FUSEKI_BASE_URL = settings.FUSEKI_URL
    FUSEKI_DATASET = settings.FUSEKI_DATASET
    FUSEKI_QUERY_URL = f"{FUSEKI_BASE_URL}/{FUSEKI_DATASET}/query"
    FUSEKI_UPDATE_URL = f"{FUSEKI_BASE_URL}/{FUSEKI_DATASET}/update"
except AttributeError as e:
    print(f"WARNING: Missing Fuseki config: {e}")
    FUSEKI_QUERY_URL = "http://localhost:3030/transport_db/query"
    FUSEKI_UPDATE_URL = "http://localhost:3030/transport_db/update"

NS = "http://www.transport-ontology.org/travel#"



def _run_sparql(query, expect_json=True, timeout=10):
    """
    Run SPARQL using sparql_query first, then HTTP fallback to FUSEKI_QUERY_URL if result empty/None.
    Returns Python dict (parsed JSON) if expect_json True, otherwise raw response text.
    """
    # Try existing wrapper
    try:
        res = sparql_query(query)
        if isinstance(res, dict):
            # If bindings present or boolean (ASK), return immediately
            if res.get('results', {}).get('bindings') or 'boolean' in res:
                return res
            # else continue to HTTP fallback
        else:
            # if wrapper returns non-dict, fall back
            pass
    except Exception as e:
        print(f"_run_sparql: sparql_query wrapper raised: {e}")

    # HTTP fallback (mimic Fuseki UI)
    try:
        headers = {'Accept': 'application/sparql-results+json'}
        resp = requests.get(FUSEKI_QUERY_URL, params={'query': query}, headers=headers, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            # sometimes ASK returns bare "true" or similar; return raw text
            return {'raw': resp.text}
    except Exception as e:
        print(f"_run_sparql: HTTP fallback failed: {e}")
        # Try encoded fallback
        try:
            qs = urlencode({'query': query})
            resp2 = requests.get(f"{FUSEKI_QUERY_URL}?{qs}", headers=headers, timeout=timeout)
            resp2.raise_for_status()
            return resp2.json()
        except Exception as e2:
            print(f"_run_sparql: HTTP encoded fallback also failed: {e2}")
            return {}
def _uri_candidates_for(full_id):
    """
    Return a list of SPARQL node strings to try when addressing the resource.
    Examples returned:
      ':I-B-014'
      '<http://www.transport-ontology.org/travel#I-B-014>'
      '<http://www.transport-ontology.org/travel#itinerary/I-B-014>'
    """
    candidates = []
    # prefixed (use colon prefix as in file)
    candidates.append(f":{full_id}")
    # absolute angle URI
    candidates.append(f"<{NS}{full_id}>")
    # legacy itinerary path
    candidates.append(f"<{NS}itinerary/{full_id}>")
    return candidates

# ----------------------------------------------------------------------
# NORMALIZE ID
# ----------------------------------------------------------------------
def normalize_itinerary_id(itinerary_id):
    """
    Normalize itinerary ID to standard format with zero-padding.
    Examples:
      6 → "006"
      "6" → "006"
      "I-B-6" → "I-B-006"
      "I-L-11" → "I-L-011"
    """
    if isinstance(itinerary_id, int):
        return f"{itinerary_id:03d}"

    if isinstance(itinerary_id, str):
        itinerary_id = itinerary_id.strip()
        if '-' in itinerary_id:
            parts = itinerary_id.split('-')
            if len(parts) >= 3:
                prefix = f"{parts[0]}-{parts[1]}"
                num = parts[2].lstrip('0') or '0'
                return f"{prefix}-{int(num):03d}"
            elif len(parts) == 1:
                return f"{int(parts[0]):03d}"
        try:
            return f"{int(itinerary_id):03d}"
        except ValueError:
            return "000"
    return "000"


# ----------------------------------------------------------------------
# ESCAPE SPARQL STRINGS
# ----------------------------------------------------------------------
def escape_sparql_string(value):
    """Escape special characters in SPARQL string literals."""
    if value is None:
        return ""
    value = str(value)
    value = value.replace('\\', '\\\\')
    value = value.replace('"', '\\"')
    value = value.replace('\n', '\\n')
    value = value.replace('\r', '\\r')
    return value


# ----------------------------------------------------------------------
# CREATE - Pure RDF (use :I-*-NNN local name)
# ----------------------------------------------------------------------
def create_itinerary(data, itinerary_type):
    """Create a new itinerary in RDF store using :I-*-NNN URIs."""
    # Set defaults
    data.setdefault('overall_status', 'Planned')
    data.setdefault('total_cost_estimate', 0.0)
    data.setdefault('total_duration_days', 1)

    # Generate full ID - match existing ontology format
    base_id = str(data.get('itinerary_id', '0')).strip()
    prefix = {'Business': 'I-B-', 'Leisure': 'I-L-', 'Educational': 'I-E-'}[itinerary_type]

    # Handle case where user might pass full ID or just number
    if base_id.startswith(('I-B-', 'I-L-', 'I-E-')):
        full_id = normalize_itinerary_id(base_id)
    else:
        try:
            normalized_base = f"{int(base_id):03d}"
        except (ValueError, TypeError):
            normalized_base = "000"
        full_id = f"{prefix}{normalized_base}"

    # Use prefixed local name (e.g., :I-B-012)
    uri = f":{full_id}"

    print(f"🔹 Creating itinerary: ID={full_id}, URI={uri}")

    # Base triples
    triples = [
        f"{uri} a :{itinerary_type}Trip .",
        f'{uri} :itineraryID "{full_id}" .',
        f'{uri} :overallStatus "{escape_sparql_string(data["overall_status"])}" .',
    ]

    # Add optional base properties
    if data.get('total_cost_estimate') is not None:
        try:
            triples.append(f'{uri} :totalCostEstimate {float(data["total_cost_estimate"]):.2f} .')
        except (ValueError, TypeError):
            triples.append(f'{uri} :totalCostEstimate 0.00 .')
    if data.get('total_duration_days') is not None:
        try:
            triples.append(f'{uri} :totalDurationDays {int(data["total_duration_days"])} .')
        except (ValueError, TypeError):
            triples.append(f'{uri} :totalDurationDays 1 .')

    # Type-specific properties
    if itinerary_type == 'Business':
        if data.get("client_project_name"):
            triples.append(f'{uri} :clientProjectName "{escape_sparql_string(data["client_project_name"])}" .')
        if data.get("expense_limit") is not None:
            try:
                triples.append(f'{uri} :expenseLimit {float(data["expense_limit"]):.2f} .')
            except (ValueError, TypeError):
                triples.append(f'{uri} :expenseLimit 0.00 .')
        if data.get("purpose_code"):
            triples.append(f'{uri} :purposeCode "{escape_sparql_string(data["purpose_code"])}" .')
        approval = str(data.get("approval_required", False)).lower()
        triples.append(f'{uri} :approvalRequired {approval} .')

    elif itinerary_type == 'Leisure':
        if data.get("activity_type"):
            triples.append(f'{uri} :activityType "{escape_sparql_string(data["activity_type"])}" .')
        if data.get("accommodation"):
            triples.append(f'{uri} :accommodation "{escape_sparql_string(data["accommodation"])}" .')
        if data.get("budget_per_day") is not None:
            try:
                triples.append(f'{uri} :budgetPerDay {float(data["budget_per_day"]):.2f} .')
            except (ValueError, TypeError):
                triples.append(f'{uri} :budgetPerDay 0.00 .')
        if data.get("group_size") is not None:
            try:
                triples.append(f'{uri} :groupSize {int(data["group_size"])} .')
            except (ValueError, TypeError):
                triples.append(f'{uri} :groupSize 1 .')

    elif itinerary_type == 'Educational':
        if data.get("institution"):
            triples.append(f'{uri} :institution "{escape_sparql_string(data["institution"])}" .')
        if data.get("course_reference"):
            triples.append(f'{uri} :courseReference "{escape_sparql_string(data["course_reference"])}" .')
        if data.get("credit_hours") is not None:
            try:
                triples.append(f'{uri} :creditHours {int(data["credit_hours"])} .')
            except (ValueError, TypeError):
                triples.append(f'{uri} :creditHours 0 .')
        if data.get("required_documentation"):
            triples.append(f'{uri} :requiredDocumentation "{escape_sparql_string(data["required_documentation"])}" .')

    # Build SPARQL query
    triples_str = '\n    '.join(triples)

    sparql = f"""
    PREFIX : <{NS}>
    INSERT DATA {{
        {triples_str}
    }}
    """

    try:
        print(f"🔹 Creating RDF with SPARQL:\n{sparql}\n")
        sparql_update(sparql)
        print(f"✅ Created RDF: {full_id} as {uri}")

        # Verify creation - check if the URI exists as the expected rdf:type
        time.sleep(0.5)
        verify_sparql = f"""
        PREFIX : <{NS}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        ASK WHERE {{
          {uri} rdf:type :{itinerary_type}Trip
        }}
        """
        print(f"🔍 Verifying with:\n{verify_sparql}\n")
        result = sparql_query(verify_sparql)
        if result.get('boolean', False):
            print(f"✅ Verification OK: {full_id} exists as {uri}")
            return full_id
        else:
            print(f"⚠️ Warning: Could not verify {uri}, but proceeding")
            return full_id

    except Exception as e:
        print(f"❌ Failed to create RDF: {e}")
        traceback.print_exc()
        raise


# ----------------------------------------------------------------------
# READ - Pure RDF (use :I-*-NNN URI pattern)
# ----------------------------------------------------------------------
def get_itinerary(itinerary_id):
    """
    Robust retrieval: try normalized ids and multiple URI candidates (prefixed and absolute),
    use wrapper _run_sparql to handle sparql_query and HTTP fallback.
    """
    itinerary_id = str(itinerary_id).strip()

    # Normalize ID set (I-B-001, I-L-001, I-E-001)
    if not itinerary_id.startswith("I-"):
        normalized = normalize_itinerary_id(itinerary_id)
        possible_ids = [
            f"I-B-{normalized}",
            f"I-L-{normalized}",
            f"I-E-{normalized}"
        ]
    else:
        possible_ids = [normalize_itinerary_id(itinerary_id)]

    for full_id in possible_ids:
        print(f"🔍 Searching for RDF: {full_id}")
        candidates = _uri_candidates_for(full_id)

        for node in candidates:
            # Build SELECT using the node (node is either prefixed like :I-B-014 or angle <...>)
            sparql = f"""
            PREFIX : <{NS}>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?prop ?val ?type WHERE {{
              {node} ?prop ?val .
              OPTIONAL {{ {node} rdf:type ?type }}
            }}
            """
            try:
                result = _run_sparql(sparql)
                bindings = result.get('results', {}).get('bindings', []) if isinstance(result, dict) else []
            except Exception as e:
                print(f"❌ SPARQL error for node {node}: {e}")
                bindings = []

            if bindings:
                data = {}
                itype = 'Business'
                for b in bindings:
                    prop_uri = b.get('prop', {}).get('value', '')
                    # get short local name if possible
                    prop = prop_uri.split('#')[-1] if '#' in prop_uri else prop_uri.split('/')[-1]
                    val = b.get('val', {}).get('value', '')
                    # store raw lexical values (later processing done by views)
                    if prop not in ['type']:
                        data[prop] = val
                    # detect rdf:type
                    if b.get('type'):
                        t = b['type']['value']
                        if 'BusinessTrip' in t:
                            itype = 'Business'
                        elif 'LeisureTrip' in t:
                            itype = 'Leisure'
                        elif 'EducationalTrip' in t:
                            itype = 'Educational'
                data['type'] = itype
                data['itineraryID'] = data.get('itineraryID', full_id)
                print(f"✅ Found RDF for {full_id} using node {node}")
                return data

    print(f"⚠️ No RDF data found for {itinerary_id}")
    return None

# ----------------------------------------------------------------------
# UPDATE - Pure RDF (use :I-*-NNN URI pattern)
# ----------------------------------------------------------------------
def update_itinerary(itinerary_id, new_data):
    """
    Update: fetch existing; merge; delete triples for all URI candidates; recreate under preferred :I-*-NNN URI.
    """
    existing = get_itinerary(itinerary_id)
    if not existing:
        print(f"⚠️ No existing RDF found for {itinerary_id}, creating new one.")
        return create_itinerary(new_data, new_data.get("type", "Business"))

    # Merge data
    merged = existing.copy()
    merged.update(new_data)
    merged.setdefault("overall_status", "Planned")
    merged.setdefault("total_cost_estimate", 0.0)
    merged.setdefault("total_duration_days", 1)

    full_id = existing.get('itineraryID', itinerary_id)
    # Delete triples for all possible URI candidates to avoid stale duplicates
    for node in _uri_candidates_for(full_id):
        delete_sparql = f"""
        PREFIX : <{NS}>
        DELETE WHERE {{ {node} ?p ?o }}
        """
        try:
            sparql_update(delete_sparql)
            print(f"🧹 Cleared old RDF data for {node}")
        except Exception as e:
            print(f"⚠️ Delete failed for {node}: {e}")

        # also remove references to the node
        delete_obj = f"""
        PREFIX : <{NS}>
        DELETE WHERE {{ ?s ?p {node} }}
        """
        try:
            sparql_update(delete_obj)
        except Exception as e:
            print(f"⚠️ Delete references failed for {node}: {e}")

    # Now recreate under preferred URI :I-*-NNN (create_itinerary expects itinerary_id in merged)
    itinerary_type = merged.get("type", "Business")
    merged["itinerary_id"] = full_id
    return create_itinerary(merged, itinerary_type)

# ----------------------------------------------------------------------
# DELETE - Pure RDF (use :I-*-NNN URI pattern)
# ----------------------------------------------------------------------
def delete_itinerary(itinerary_id):
    """
    Delete resource: attempt to resolve full_id, then delete triples for all URI candidates and references.
    """
    original_id = str(itinerary_id).strip()
    existing = get_itinerary(original_id)
    if existing:
        full_id = existing.get('itineraryID', original_id)
    else:
        normalized = normalize_itinerary_id(original_id)
        full_id = f"I-B-{normalized}" if not original_id.startswith("I-") else normalized

    print(f"\n🧹 Deleting itinerary: {original_id} (normalized: {full_id})")

    success = True
    for node in _uri_candidates_for(full_id):
        try:
            delete_subject = f"""
            PREFIX : <{NS}>
            DELETE WHERE {{ {node} ?p ?o }}
            """
            sparql_update(delete_subject)
            print(f"✅ Deleted triples for: {node}")
        except Exception as e:
            print(f"❌ Delete failed for {node}: {e}")
            success = False

        try:
            delete_object = f"""
            PREFIX : <{NS}>
            DELETE WHERE {{ ?s ?p {node} }}
            """
            sparql_update(delete_object)
            print(f"✅ Deleted references to: {node}")
        except Exception as e:
            print(f"❌ Delete references failed for {node}: {e}")
            success = False

    # Verification: check if any candidate still exists
    time.sleep(0.3)
    any_exists = False
    for node in _uri_candidates_for(full_id):
        ask_q = f"""
        PREFIX : <{NS}>
        ASK WHERE {{ {node} ?p ?o }}
        """
        res = _run_sparql(ask_q)
        if isinstance(res, dict) and res.get('boolean', False):
            any_exists = True
            print(f"⚠️ Still exists: {node}")
            break

    if any_exists:
        print(f"⚠️ WARNING: {full_id} still exists in RDF!")
        return False
    else:
        print(f"🎯 CONFIRMED: {full_id} fully deleted")
        return success


# ----------------------------------------------------------------------
# LIST - Pure RDF (uses the working SPARQL)
# ----------------------------------------------------------------------
def list_itineraries(filters=None):
    """
    List all itineraries from RDF store with optional filters.
    - First tries existing sparql_query(...)
    - If that returns empty bindings, falls back to a direct HTTP GET to FUSEKI_QUERY_URL
      with Accept: application/sparql-results+json so we mimic Fuseki UI behavior.
    """
    sparql = f"""
    PREFIX : <{NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT DISTINCT ?s ?id ?status ?cost ?duration ?type WHERE {{
      ?s :itineraryID ?id .
      OPTIONAL {{ ?s rdf:type ?type }}
      OPTIONAL {{ ?s :overallStatus ?status }}
      OPTIONAL {{ ?s :totalCostEstimate ?cost }}
      OPTIONAL {{ ?s :totalDurationDays ?duration }}
      FILTER( !BOUND(?type) || ?type = :BusinessTrip || ?type = :LeisureTrip || ?type = :EducationalTrip )
    }}
    ORDER BY ?id
    LIMIT 200
    """

    print("Running LIST SPARQL via sparql_query:\n", sparql)
    result = None
    try:
        result = sparql_query(sparql)
        print("Raw SPARQL result from sparql_query:", result)
    except Exception as e:
        print("sparql_query raised exception:", e)

    bindings = []
    if isinstance(result, dict):
        bindings = result.get('results', {}).get('bindings', []) or []

    # If sparql_query returned no bindings, try direct HTTP to Fuseki (fallback)
    if not bindings:
        print("No bindings from sparql_query — attempting HTTP fallback to FUSEKI_QUERY_URL")
        try:
            headers = {'Accept': 'application/sparql-results+json'}
            # Use GET with 'query' param (Fuseki supports GET)
            resp = requests.get(FUSEKI_QUERY_URL, params={'query': sparql}, headers=headers, timeout=10)
            print("HTTP GET ->", resp.status_code, resp.url)
            resp.raise_for_status()
            http_result = resp.json()
            print("Raw SPARQL result from HTTP fallback:", http_result)
            bindings = http_result.get('results', {}).get('bindings', []) or []
        except Exception as e:
            print("HTTP fallback failed:", e)
            # As last resort, try the URL-encoded GET (some Fuseki setups require URL encoded query)
            try:
                qs = urlencode({'query': sparql})
                resp2 = requests.get(f"{FUSEKI_QUERY_URL}?{qs}", headers=headers, timeout=10)
                print("HTTP GET (encoded) ->", resp2.status_code, resp2.url)
                resp2.raise_for_status()
                http_result2 = resp2.json()
                print("Raw SPARQL result from HTTP fallback (encoded):", http_result2)
                bindings = http_result2.get('results', {}).get('bindings', []) or []
            except Exception as e2:
                print("HTTP fallback (encoded) also failed:", e2)
                bindings = []

    print(f"Found {len(bindings)} raw bindings (after fallback attempts)")

    rows = []
    for b in bindings:
        iid = b.get('id', {}).get('value', '')
        if not iid:
            print("Skipping entry with empty id binding:", b)
            continue

        type_uri = b.get('type', {}).get('value', '')
        if type_uri:
            type_name = type_uri.split('#')[-1].replace('Trip', '')
        else:
            uid = iid.upper()
            if uid.startswith("I-B-"):
                type_name = "Business"
            elif uid.startswith("I-L-"):
                type_name = "Leisure"
            elif uid.startswith("I-E-"):
                type_name = "Educational"
            else:
                type_name = "Unknown"

        status = b.get('status', {}).get('value', 'Unknown')
        cost_val = b.get('cost', {}).get('value', None)
        if cost_val is None or cost_val == '':
            cost_str = "0.00"
        else:
            try:
                cost_str = f"{float(cost_val):.2f}"
            except (ValueError, TypeError):
                cost_str = str(cost_val)

        dur_val = b.get('duration', {}).get('value', None)
        if dur_val is None or dur_val == '':
            duration_str = "1"
        else:
            try:
                duration_str = str(int(float(dur_val)))
            except (ValueError, TypeError):
                duration_str = str(dur_val)

        row = {
            "id": iid,
            "status": status,
            "cost": cost_str,
            "duration": duration_str,
            "type": type_name,
        }

        # Apply filters
        if filters:
            if filters.get('type') and filters['type'].strip().title() != row['type']:
                continue
            if filters.get('status') and filters['status'].strip() != row['status']:
                continue
            if filters.get('cost_lt'):
                try:
                    if float(row['cost']) >= float(filters['cost_lt']):
                        continue
                except (ValueError, TypeError):
                    pass
            if filters.get('cost_gt'):
                try:
                    if float(row['cost']) <= float(filters['cost_gt']):
                        continue
                except (ValueError, TypeError):
                    pass

        rows.append(row)

    print(f"Final: Listed {len(rows)} itineraries: {[r['id'] for r in rows]}")
    return rows
