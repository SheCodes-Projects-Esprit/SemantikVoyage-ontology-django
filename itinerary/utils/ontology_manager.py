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



def _run_sparql(query, expect_json=True, timeout=10, all_graphs=False):
    """
    Run SPARQL using sparql_query first, then HTTP fallback to FUSEKI_QUERY_URL if result empty/None.
    If all_graphs=True, bypasses sparql_query and uses HTTP GET directly to search ALL graphs.
    Returns Python dict (parsed JSON) if expect_json True, otherwise raw response text.
    """
    # If all_graphs=True, skip sparql_query (which adds default-graph-uri) and go straight to HTTP
    if all_graphs:
        try:
            headers = {'Accept': 'application/sparql-results+json'}
            # Use HTTP GET directly without default-graph-uri to search ALL graphs
            resp = requests.get(FUSEKI_QUERY_URL, params={'query': query}, headers=headers, timeout=timeout)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {'raw': resp.text}
        except Exception as e:
            print(f"_run_sparql (all_graphs): HTTP direct failed: {e}")
            return {}
    
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

    # HTTP fallback (mimic Fuseki UI) - also without default-graph-uri
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
    # Strategy: Search in ALL graphs (default + configured graph) to find ALL itineraries
    # This combines results from both the ontology file (default graph) and newly created ones (named graph)
    
    all_bindings = []
    seen_subjects = set()  # Track by subject URI to avoid duplicates across queries
    
    # Query 1: Search WITHOUT GRAPH restriction (finds everything including default graph)
    query1 = f"""
    PREFIX : <{NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22/rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?s ?id ?status ?cost ?duration ?type WHERE {{
      {{
        # Match by type first - catches all itineraries including new ones
        ?s rdf:type/rdfs:subClassOf* :Itinerary .
        OPTIONAL {{ ?s :itineraryID ?id }}
      }}
      UNION
      {{
        # Also match by itineraryID if type matching didn't work
        ?s :itineraryID ?id .
        OPTIONAL {{ ?s rdf:type/rdfs:subClassOf* :Itinerary }}
      }}
      OPTIONAL {{ ?s rdf:type ?type }}
      OPTIONAL {{ ?s :overallStatus ?status }}
      OPTIONAL {{ ?s :totalCostEstimate ?cost }}
      OPTIONAL {{ ?s :totalDurationDays ?duration }}
    }}
    ORDER BY ?id
    LIMIT 500
    """
    
    print("🔍 Query 1: Searching ALL graphs (no GRAPH restriction, no default-graph-uri)...")
    try:
        # Use all_graphs=True to bypass sparql_query and search ALL graphs
        result1 = _run_sparql(query1, all_graphs=True)
        if isinstance(result1, dict):
            bindings1 = result1.get('results', {}).get('bindings', []) or []
            print(f"✅ Query 1 returned {len(bindings1)} bindings")
            for b in bindings1:
                s_uri = b.get('s', {}).get('value', '') if isinstance(b.get('s'), dict) else str(b.get('s', ''))
                if s_uri and s_uri not in seen_subjects:
                    all_bindings.append(b)
                    seen_subjects.add(s_uri)
        else:
            print("⚠️ Query 1 returned non-dict result")
    except Exception as e:
        print(f"❌ Query 1 failed: {e}")
        traceback.print_exc()
    
    # Query 2: If graph URI configured, also search explicitly in that graph (to catch any missed)
    try:
        graph_uri = getattr(settings, 'FUSEKI_GRAPH', None)
        if graph_uri:
            query2 = f"""
            PREFIX : <{NS}>
            PREFIX rdf: <http://www.w3.org/1999/02/22/rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT DISTINCT ?s ?id ?status ?cost ?duration ?type WHERE {{
              GRAPH <{graph_uri}> {{
                {{
                  ?s rdf:type/rdfs:subClassOf* :Itinerary .
                  OPTIONAL {{ ?s :itineraryID ?id }}
                }}
                UNION
                {{
                  ?s :itineraryID ?id .
                  OPTIONAL {{ ?s rdf:type/rdfs:subClassOf* :Itinerary }}
                }}
                OPTIONAL {{ ?s rdf:type ?type }}
                OPTIONAL {{ ?s :overallStatus ?status }}
                OPTIONAL {{ ?s :totalCostEstimate ?cost }}
                OPTIONAL {{ ?s :totalDurationDays ?duration }}
              }}
            }}
            ORDER BY ?id
            LIMIT 500
            """
            
            print(f"🔍 Query 2: Searching explicitly in GRAPH <{graph_uri}>...")
            try:
                # Also use all_graphs=True to ensure we search in the named graph
                result2 = _run_sparql(query2, all_graphs=True)
                if isinstance(result2, dict):
                    bindings2 = result2.get('results', {}).get('bindings', []) or []
                    print(f"✅ Query 2 returned {len(bindings2)} bindings")
                    for b in bindings2:
                        s_uri = b.get('s', {}).get('value', '') if isinstance(b.get('s'), dict) else str(b.get('s', ''))
                        if s_uri and s_uri not in seen_subjects:
                            all_bindings.append(b)
                            seen_subjects.add(s_uri)
            except Exception as e:
                print(f"❌ Query 2 failed: {e}")
    except Exception as e:
        print(f"⚠️ Error setting up graph query: {e}")
    
    bindings = all_bindings
    print(f"📊 Total unique bindings after combining queries: {len(bindings)}")

    print(f"📊 Found {len(bindings)} raw bindings")
    
    if not bindings:
        print("⚠️ WARNING: No bindings returned from SPARQL query!")
        return []

    rows = []
    seen_ids = set()  # Track seen IDs to avoid duplicates

    for idx, b in enumerate(bindings):
        print(f"🔍 Processing binding {idx + 1}/{len(bindings)}: {b}")
        
        # Extract itinerary ID - handle both dict and direct values
        iid_obj = b.get('id', {})
        iid = iid_obj.get('value', '') if isinstance(iid_obj, dict) else str(iid_obj) if iid_obj else ''
        
        # If no ID from property, try to extract from subject URI
        if not iid:
            s_obj = b.get('s', {})
            s_uri = s_obj.get('value', '') if isinstance(s_obj, dict) else str(s_obj) if s_obj else ''
            print(f"  🔍 No ID from property, trying to extract from URI: {s_uri}")
            # Try to extract ID from URI (e.g., .../travel#I-B-001 or .../travel#itinerary/I-E-005)
            if s_uri:
                if '#' in s_uri:
                    local_part = s_uri.split('#')[-1]
                    # Handle cases like "itinerary/I-E-005" - extract just the ID part
                    if '/' in local_part:
                        # Extract last part after slash (e.g., "I-E-005" from "itinerary/I-E-005")
                        potential_id = local_part.split('/')[-1]
                        print(f"  🔍 Extracted potential ID from path: {potential_id}")
                        if potential_id.startswith(('I-B-', 'I-L-', 'I-E-')):
                            iid = potential_id
                    elif local_part.startswith(('I-B-', 'I-L-', 'I-E-')):
                        iid = local_part
                    elif local_part.startswith('I-'):
                        iid = local_part
                elif '/' in s_uri:
                    local_part = s_uri.split('/')[-1]
                    if local_part.startswith(('I-B-', 'I-L-', 'I-E-')):
                        iid = local_part
        
        if not iid:
            print(f"⚠️ Skipping entry {idx + 1} with empty id. Binding: {b}")
            continue
        
        print(f"  ✅ Extracted ID: {iid}")

        # Skip duplicates
        if iid in seen_ids:
            continue
        seen_ids.add(iid)

        # Determine type
        type_obj = b.get('type', {})
        type_value = type_obj.get('value', '') if isinstance(type_obj, dict) else str(type_obj) if type_obj else ''
        
        if type_value:
            # Extract type name from URI
            if 'BusinessTrip' in type_value or 'Business' in type_value:
                type_name = "Business"
            elif 'LeisureTrip' in type_value or 'Leisure' in type_value:
                type_name = "Leisure"
            elif 'EducationalTrip' in type_value or 'Educational' in type_value:
                type_name = "Educational"
            else:
                type_name = "Unknown"
        else:
            # Infer type from ID
            uid = iid.upper()
            if uid.startswith("I-B-"):
                type_name = "Business"
            elif uid.startswith("I-L-"):
                type_name = "Leisure"
            elif uid.startswith("I-E-"):
                type_name = "Educational"
            else:
                type_name = "Unknown"

        # Extract status
        status_obj = b.get('status', {})
        status = status_obj.get('value', 'Unknown') if isinstance(status_obj, dict) else str(status_obj) if status_obj else 'Unknown'

        # Extract cost - handle typed values
        cost_obj = b.get('cost', {})
        cost_val = cost_obj.get('value', None) if isinstance(cost_obj, dict) else cost_obj
        if cost_val is None or cost_val == '':
            cost_str = "0.00"
        else:
            try:
                cost_str = f"{float(cost_val):.2f}"
            except (ValueError, TypeError):
                cost_str = str(cost_val) if cost_val else "0.00"

        # Extract duration - handle typed values
        dur_obj = b.get('duration', {})
        dur_val = dur_obj.get('value', None) if isinstance(dur_obj, dict) else dur_obj
        if dur_val is None or dur_val == '':
            duration_str = "1"
        else:
            try:
                duration_str = str(int(float(dur_val)))
            except (ValueError, TypeError):
                duration_str = str(dur_val) if dur_val else "1"

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
        print(f"  ✅ Added row: {row}")

    # Sort by ID to ensure consistent ordering
    rows.sort(key=lambda x: x["id"])

    print(f"✅ Final: Listed {len(rows)} itineraries (from {len(bindings)} bindings)")
    print(f"   IDs: {[r['id'] for r in rows[:10]]}{'...' if len(rows) > 10 else ''}")
    if len(rows) == 0:
        print("⚠️ WARNING: No rows created! Check the bindings processing above.")
    return rows
