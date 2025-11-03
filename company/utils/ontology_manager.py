# Complete replacement for company/utils/ontology_manager.py
# This ensures ALL functions use the named graph correctly

import time
from rdflib.plugins.stores.sparqlstore import SPARQLStore, SPARQLUpdateStore
from rdflib import Graph
import requests

SPARQL_PREFIXES = """
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

NS = "http://www.transport-ontology.org/travel#"
GRAPH_URI = "http://www.transport-ontology.org/travel"
FUSEKI_QUERY_URL = "http://localhost:3030/transport_db/query"
FUSEKI_UPDATE_URL = "http://localhost:3030/transport_db/update"


def _run_query(query: str):
    """Query default graph only (for backward compatibility)"""
    store = SPARQLStore(FUSEKI_QUERY_URL)
    g = Graph(store=store)
    res = g.query(SPARQL_PREFIXES + query)
    vars_ = [str(v) for v in res.vars]
    bindings = []
    for row in res:
        b = {}
        for i, v in enumerate(vars_):
            term = row[i]
            if term is None:
                continue
            val = str(term)
            b[v] = {"type": "uri" if val.startswith('http') else "literal", "value": val}
        bindings.append(b)
    return {"results": {"bindings": bindings}}


def query_all_graphs(sparql: str):
    """Query across ALL graphs (default + named) - preferred for reading"""
    headers = {'Accept': 'application/sparql-results+json'}
    try:
        resp = requests.get(FUSEKI_QUERY_URL, params={'query': SPARQL_PREFIXES + sparql}, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[company/query_all_graphs] Error: {e}")
        return {"results": {"bindings": []}}


def _run_update(update: str):
    """Basic update to default graph (legacy, avoid using)"""
    print(f"[DEBUG] Running SPARQL UPDATE:\n{update}")
    store = SPARQLUpdateStore()
    store.open((FUSEKI_QUERY_URL, FUSEKI_UPDATE_URL))
    try:
        store.update(update)
        print("[SUCCESS] Update sent to Fuseki!")
    except Exception as e:
        print(f"[FUSEKI ERROR] {e}")
        raise e
    finally:
        try:
            store.close()
        except:
            pass


def run_sparql_update(sparql_query: str):
    """
    Execute any SPARQL UPDATE query (DELETE, INSERT, DELETE/INSERT WHERE, etc.)
    Handles both default graph and named graph operations.
    """
    import requests
    
    print(f"[run_sparql_update] Executing:\n{sparql_query}")
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {'update': SPARQL_PREFIXES + sparql_query}
    
    try:
        resp = requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=20)
        if resp.status_code not in [200, 204]:
            raise Exception(f"Fuseki update failed: {resp.status_code} - {resp.text}")
        print("[run_sparql_update] ✓ Update successful!")
        return True
    except Exception as e:
        print(f"[run_sparql_update] ✗ Error: {e}")
        raise


def update_company_property(company_name: str, property_updates: dict):
    """
    Update specific properties of a company without recreating the entire entity.
    
    Args:
        company_name: Name of the company to update
        property_updates: Dict of property_name -> new_value
                         e.g., {'employees': 5000, 'headquarters': 'Tunis'}
    """
    property_map = {
        'employees': ':numberOfEmployees',
        'year': ':foundedYear',
        'headquarters': ':headquartersLocation',
        'hq': ':headquartersLocation',
        'buslines': ':numberOfBusLines',
        'lines': ':numberOfLines',
        'vehicles': ':numberOfVehicles',
        'stations': ':numberOfStations',
        'bikes': ':bikeCount',
        'fare': ':averageFarePerKm',
        'ticket': ':ticketPrice',
        'trackLength': ':totalTrackLength',
        'track': ':totalTrackLength',
        'automation': ':automationLevel',
        'passengers': ':dailyPassengers',
        'app': ':hasBookingApp',
        'eco': ':ecoFriendlyFleet',
        'electric': ':electricBikes',
        'price': ':subscriptionPrice',
        'bugage': ':averageBusAge',
        'age': ':averageBusAge',
    }
    
    uri = f":company_{company_name.replace(' ', '_')}"
    
    delete_clauses = []
    insert_clauses = []
    
    for prop_key, new_value in property_updates.items():
        rdf_prop = property_map.get(prop_key.lower())
        
        if not rdf_prop:
            # Try partial match
            for key, val in property_map.items():
                if key in prop_key.lower() or prop_key.lower() in key:
                    rdf_prop = val
                    break
        
        if not rdf_prop:
            print(f"[WARNING] Unknown property: {prop_key}")
            continue
        
        # Format value based on type
        if isinstance(new_value, bool) or str(new_value).lower() in ['true', 'false']:
            formatted_value = str(new_value).lower()
        elif isinstance(new_value, (int, float)):
            formatted_value = str(new_value)
        elif str(new_value).replace('.', '').replace('-', '').isdigit():
            formatted_value = str(new_value)
        else:
            formatted_value = f'"{escape_sparql_string(str(new_value))}"'
        
        delete_clauses.append(f"    {uri} {rdf_prop} ?old_{prop_key} .")
        insert_clauses.append(f"    {uri} {rdf_prop} {formatted_value} .")
    
    if not delete_clauses:
        raise ValueError("No valid properties to update")
    
    # Build the SPARQL update for NAMED graph
    sparql = f"""
WITH <{GRAPH_URI}>
DELETE {{
{chr(10).join(delete_clauses)}
}}
INSERT {{
{chr(10).join(insert_clauses)}
}}
WHERE {{
  {uri} a ?type .
  {chr(10).join([f"  OPTIONAL {{ {clause} }}" for clause in delete_clauses])}
}}
"""
    
    run_sparql_update(sparql)
    
    # Also update in default graph if it exists there
    sparql_default = f"""
DELETE {{
{chr(10).join(delete_clauses)}
}}
INSERT {{
{chr(10).join(insert_clauses)}
}}
WHERE {{
  {uri} a ?type .
  {chr(10).join([f"  OPTIONAL {{ {clause} }}" for clause in delete_clauses])}
}}
"""
    
    try:
        run_sparql_update(sparql_default)
    except:
        pass  # Ignore if not in default graph
    
    return True



def company_sparql_update(triples: str):
    """
    Company-scoped SPARQL UPDATE that guarantees using the ontology named graph.
    Takes raw triples (without INSERT DATA wrapper) and properly formats them.
    
    Args:
        triples: Raw RDF triples like ":company_X a :BusCompany ; :companyName 'X' ."
    """
    # Clean up any accidental wrapper keywords from LLM
    text = triples.strip()
    if 'INSERT DATA' in text.upper():
        # Extract just the triples
        import re
        match = re.search(r'INSERT\s+DATA\s*\{(.+)\}', text, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1).strip()
        # Remove GRAPH wrapper if present
        match = re.search(r'GRAPH\s*<[^>]+>\s*\{(.+)\}', text, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1).strip()
    
    # Build the proper INSERT DATA with GRAPH
    sparql = f"""
INSERT DATA {{
  GRAPH <{GRAPH_URI}> {{
    {text}
  }}
}}
"""
    
    print(f"[DEBUG] Executing SPARQL:\n{sparql}")
    
    # Use requests directly for better error messages
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {'update': SPARQL_PREFIXES + sparql}
    
    try:
        resp = requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=20)
        if resp.status_code != 200:
            raise Exception(f"Fuseki update failed: {resp.status_code} - {resp.text}")
        print("[SUCCESS] Company update executed!")
        return True
    except Exception as e:
        print(f"[company_sparql_update] Error: {e}")
        raise


def escape_sparql_string(value):
    if value is None:
        return ""
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def _resolve_company_subject_by_name(name: str):
    """Return a SPARQL node for the company resource that has :companyName name."""
    sname = escape_sparql_string(name)
    q = f"""
    SELECT ?s ?type WHERE {{
      ?s :companyName "{sname}" .
      OPTIONAL {{ ?s rdf:type ?type }}
    }} LIMIT 1
    """
    # Use query_all_graphs to find companies in named graph
    res = query_all_graphs(q)
    bindings = res.get('results', {}).get('bindings', [])
    if not bindings:
        return None, None
    s_val = bindings[0].get('s', {}).get('value')
    t_val = bindings[0].get('type', {}).get('value', '')
    node = f"<{s_val}>" if s_val else None
    return node, t_val


def create_company(data):
    name = (data.get('name') or '').strip()
    if not name:
        raise ValueError("Company name is required!")

    uri = f":company_{name.replace(' ', '_')}"

    # Note: Ontology uses subclass types for companies. If 'type' provided, set it; else default :Company
    company_type = str(data.get('type') or 'Company')
    triples = f"{uri} a :{company_type} ;\n      :companyName \"{escape_sparql_string(name)}\""

    # Common properties in ontology
    if data.get('number_of_employees') not in (None, ""):
        try:
            triples += f" ;\n      :numberOfEmployees {int(data['number_of_employees'])}"
        except (ValueError, TypeError):
            pass
    if data.get('founded_year'):
        triples += f" ;\n      :foundedYear \"{escape_sparql_string(data['founded_year'])}\""
    if data.get('headquarters_location'):
        triples += f" ;\n      :headquartersLocation \"{escape_sparql_string(data['headquarters_location'])}\""

    # Subclass specific
    if company_type == 'BusCompany':
        if data.get('number_of_bus_lines') not in (None, ""):
            triples += f" ;\n      :numberOfBusLines {int(data['number_of_bus_lines'])}"
        if data.get('average_bus_age') not in (None, ""):
            triples += f" ;\n      :averageBusAge {float(data['average_bus_age']):.1f}"
        if data.get('ticket_price') not in (None, ""):
            triples += f" ;\n      :ticketPrice {float(data['ticket_price']):.2f}"
        if str(data.get('eco_friendly_fleet', '')).lower() in ['true', 'false']:
            triples += f" ;\n      :ecoFriendlyFleet {str(data['eco_friendly_fleet']).lower()}"
    elif company_type == 'MetroCompany':
        if data.get('number_of_lines') not in (None, ""):
            triples += f" ;\n      :numberOfLines {int(data['number_of_lines'])}"
        if data.get('total_track_length') not in (None, ""):
            triples += f" ;\n      :totalTrackLength {float(data['total_track_length']):.1f}"
        if data.get('automation_level'):
            triples += f" ;\n      :automationLevel \"{escape_sparql_string(data['automation_level'])}\""
        if data.get('daily_passengers') not in (None, ""):
            triples += f" ;\n      :dailyPassengers {int(data['daily_passengers'])}"
    elif company_type == 'TaxiCompany':
        if data.get('number_of_vehicles') not in (None, ""):
            triples += f" ;\n      :numberOfVehicles {int(data['number_of_vehicles'])}"
        if str(data.get('booking_app', '')).lower() in ['true', 'false']:
            triples += f" ;\n      :hasBookingApp {str(data['booking_app']).lower()}"
        if data.get('average_fare_per_km') not in (None, ""):
            triples += f" ;\n      :averageFarePerKm {float(data['average_fare_per_km']):.2f}"
    elif company_type == 'BikeSharingCompany':
        if data.get('number_of_stations') not in (None, ""):
            triples += f" ;\n      :numberOfStations {int(data['number_of_stations'])}"
        if data.get('bike_count') not in (None, ""):
            triples += f" ;\n      :bikeCount {int(data['bike_count'])}"
        if data.get('subscription_price') not in (None, ""):
            triples += f" ;\n      :subscriptionPrice {float(data['subscription_price']):.2f}"
        if str(data.get('electric_bikes', '')).lower() in ['true', 'false']:
            triples += f" ;\n      :electricBikes {str(data['electric_bikes']).lower()}"

    triples += " ."

    # Use company_sparql_update to write to named graph
    company_sparql_update(triples)
    time.sleep(0.3)  # Give Fuseki time to index
    return name


def get_company(name):
    # Try synthetic URI first across all graphs
    uri = f":company_{str(name).replace(' ', '_')}"
    q_direct = f"""
    SELECT ?prop ?val WHERE {{
      {uri} ?prop ?val .
      FILTER(isIRI(?val) || isLiteral(?val))
    }}
    """
    results = query_all_graphs(q_direct)
    rows = [(b['prop']['value'], b['val']['value']) for b in results.get('results', {}).get('bindings', [])]
    
    # Fallback: resolve by companyName
    if not rows:
        node, t_val = _resolve_company_subject_by_name(name)
        if not node:
            return None
        q_byname = f"""
        SELECT ?prop ?val WHERE {{
          {node} ?prop ?val .
          FILTER(isIRI(?val) || isLiteral(?val))
        }}
        """
        results = query_all_graphs(q_byname)
        rows = [(b['prop']['value'], b['val']['value']) for b in results.get('results', {}).get('bindings', [])]

    if not rows:
        return None

    data = {'name': name}
    ctype = 'Company'
    for prop_term, val_term in rows:
        prop = str(prop_term).split('#')[-1]
        val = str(val_term)
        if prop == 'type':
            if 'BusCompany' in val: ctype = 'BusCompany'
            elif 'MetroCompany' in val: ctype = 'MetroCompany'
            elif 'TaxiCompany' in val: ctype = 'TaxiCompany'
            elif 'BikeSharingCompany' in val: ctype = 'BikeSharingCompany'
        elif prop == 'companyName':
            data['name'] = val
        elif prop == 'foundedYear':
            data['founded_year'] = val
        elif prop == 'headquartersLocation':
            data['headquarters_location'] = val
        elif prop == 'numberOfEmployees':
            data['number_of_employees'] = val
        # Subclass specific
        elif prop == 'numberOfBusLines':
            data['number_of_bus_lines'] = val
        elif prop == 'averageBusAge':
            data['average_bus_age'] = val
        elif prop == 'ticketPrice':
            data['ticket_price'] = val
        elif prop == 'ecoFriendlyFleet':
            data['eco_friendly_fleet'] = val
        elif prop == 'numberOfLines':
            data['number_of_lines'] = val
        elif prop == 'totalTrackLength':
            data['total_track_length'] = val
        elif prop == 'automationLevel':
            data['automation_level'] = val
        elif prop == 'dailyPassengers':
            data['daily_passengers'] = val
        elif prop == 'numberOfVehicles':
            data['number_of_vehicles'] = val
        elif prop == 'hasBookingApp':
            data['booking_app'] = val
        elif prop == 'averageFarePerKm':
            data['average_fare_per_km'] = val
        elif prop == 'numberOfStations':
            data['number_of_stations'] = val
        elif prop == 'bikeCount':
            data['bike_count'] = val
        elif prop == 'subscriptionPrice':
            data['subscription_price'] = val
        elif prop == 'electricBikes':
            data['electric_bikes'] = val
        else:
            data[prop] = val
    data['type'] = ctype
    return data


def list_companies():
    """
    List companies from BOTH default graph AND named graph
    CRITICAL FIX: Uses full URIs to handle namespace inconsistencies
    """
    # Use full URIs instead of prefixes to avoid namespace issues
    q = """
    SELECT ?name ?type ?employees ?year ?hq ?busLines ?metroLines ?vehicles ?stations WHERE {
      {
        # Default graph - try both namespace patterns
        ?s rdf:type/rdfs:subClassOf* :Company .
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/companyName> ?name }
          UNION
          { ?s <http://www.transport-ontology.org/travel#companyName> ?name }
        }
        OPTIONAL { ?s rdf:type ?type }
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/numberOfEmployees> ?employees }
          UNION
          { ?s <http://www.transport-ontology.org/travel#numberOfEmployees> ?employees }
        }
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/foundedYear> ?year }
          UNION
          { ?s <http://www.transport-ontology.org/travel#foundedYear> ?year }
        }
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/headquartersLocation> ?hq }
          UNION
          { ?s <http://www.transport-ontology.org/travel#headquartersLocation> ?hq }
        }
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/numberOfBusLines> ?busLines }
          UNION
          { ?s <http://www.transport-ontology.org/travel#numberOfBusLines> ?busLines }
        }
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/numberOfLines> ?metroLines }
          UNION
          { ?s <http://www.transport-ontology.org/travel#numberOfLines> ?metroLines }
        }
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/numberOfVehicles> ?vehicles }
          UNION
          { ?s <http://www.transport-ontology.org/travel#numberOfVehicles> ?vehicles }
        }
        OPTIONAL { 
          { ?s <http://www.transport-ontology.org/numberOfStations> ?stations }
          UNION
          { ?s <http://www.transport-ontology.org/travel#numberOfStations> ?stations }
        }
      }
      UNION
      {
        # Named graph - try both namespace patterns
        GRAPH <http://www.transport-ontology.org/travel> {
          ?s rdf:type/rdfs:subClassOf* :Company .
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/companyName> ?name }
            UNION
            { ?s <http://www.transport-ontology.org/travel#companyName> ?name }
          }
          OPTIONAL { ?s rdf:type ?type }
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/numberOfEmployees> ?employees }
            UNION
            { ?s <http://www.transport-ontology.org/travel#numberOfEmployees> ?employees }
          }
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/foundedYear> ?year }
            UNION
            { ?s <http://www.transport-ontology.org/travel#foundedYear> ?year }
          }
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/headquartersLocation> ?hq }
            UNION
            { ?s <http://www.transport-ontology.org/travel#headquartersLocation> ?hq }
          }
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/numberOfBusLines> ?busLines }
            UNION
            { ?s <http://www.transport-ontology.org/travel#numberOfBusLines> ?busLines }
          }
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/numberOfLines> ?metroLines }
            UNION
            { ?s <http://www.transport-ontology.org/travel#numberOfLines> ?metroLines }
          }
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/numberOfVehicles> ?vehicles }
            UNION
            { ?s <http://www.transport-ontology.org/travel#numberOfVehicles> ?vehicles }
          }
          OPTIONAL { 
            { ?s <http://www.transport-ontology.org/numberOfStations> ?stations }
            UNION
            { ?s <http://www.transport-ontology.org/travel#numberOfStations> ?stations }
          }
        }
      }
      FILTER(BOUND(?name))
    }
    ORDER BY ?name
    """
    
    # Use query_all_graphs (which doesn't restrict to default graph)
    results = query_all_graphs(q)
    rows = []
    seen_names = set()  # Avoid duplicates if company exists in both graphs
    
    for b in results.get('results', {}).get('bindings', []):
        name = b.get('name', {}).get('value', '')
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        
        t = b.get('type', {}).get('value', '')
        ctype = 'Company'
        if 'BusCompany' in t: ctype = 'Bus'
        elif 'MetroCompany' in t: ctype = 'Metro'
        elif 'TaxiCompany' in t: ctype = 'Taxi'
        elif 'BikeSharingCompany' in t: ctype = 'BikeSharing'
        
        rows.append({
            "name": name,
            "type": ctype,
            "employees": b.get('employees', {}).get('value'),
            "year": b.get('year', {}).get('value'),
            "hq": b.get('hq', {}).get('value'),
            "busLines": b.get('busLines', {}).get('value'),
            "metroLines": b.get('metroLines', {}).get('value'),
            "vehicles": b.get('vehicles', {}).get('value'),
            "stations": b.get('stations', {}).get('value'),
        })
    return rows


def delete_company(name):
    """
    Delete company - handles BOTH namespace patterns
    Uses full URIs to avoid prefix issues
    """
    import requests
    
    escaped_name = escape_sparql_string(name)
    
    # Search with BOTH namespace patterns using full URIs
    find_query = f"""
SELECT ?company WHERE {{
  {{
    # Search in default graph with both namespaces
    {{
      ?company <http://www.transport-ontology.org/companyName> "{escaped_name}" .
    }}
    UNION
    {{
      ?company <http://www.transport-ontology.org/travel#companyName> "{escaped_name}" .
    }}
  }}
  UNION
  {{
    # Search in named graph with both namespaces
    GRAPH <http://www.transport-ontology.org/travel> {{
      {{
        ?company <http://www.transport-ontology.org/companyName> "{escaped_name}" .
      }}
      UNION
      {{
        ?company <http://www.transport-ontology.org/travel#companyName> "{escaped_name}" .
      }}
    }}
  }}
}}
"""
    
    print(f"\n[DELETE] Searching for company '{name}' with both namespace patterns...")
    
    # Query directly with requests (no prefixes to avoid confusion)
    headers = {'Accept': 'application/sparql-results+json'}
    try:
        resp = requests.get(
            FUSEKI_QUERY_URL, 
            params={'query': find_query}, 
            headers=headers, 
            timeout=15
        )
        resp.raise_for_status()
        results = resp.json()
        bindings = results.get('results', {}).get('bindings', [])
        print(f"[DELETE] Found {len(bindings)} instance(s)")
        
        for b in bindings:
            print(f"  - {b.get('company', {}).get('value')}")
            
    except Exception as e:
        print(f"[DELETE ERROR] Search failed: {e}")
        return False
    
    if not bindings:
        print(f"[DELETE] ❌ No company found with name '{name}'")
        return False
    
    # Step 2: Delete each found URI from ALL possible locations
    deleted_count = 0
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    for binding in bindings:
        uri = binding.get('company', {}).get('value', '')
        
        if not uri:
            continue
        
        print(f"\n[DELETE] Deleting: {uri}")
        
        # Delete from default graph
        delete_default = f"DELETE WHERE {{ <{uri}> ?p ?o }}"
        try:
            payload = {'update': delete_default}
            resp = requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=15)
            if resp.status_code in [200, 204]:
                print(f"[DELETE] ✓ Deleted from default graph")
                deleted_count += 1
            else:
                print(f"[DELETE] Default graph delete returned: {resp.status_code}")
        except Exception as e:
            print(f"[DELETE] Default graph error: {e}")
        
        # Delete from named graph - CRITICAL FIX
        delete_named = f"""
DELETE WHERE {{
  GRAPH <http://www.transport-ontology.org/travel> {{
    <{uri}> ?p ?o
  }}
}}
"""
        try:
            payload = {'update': delete_named}
            resp = requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=15)
            if resp.status_code in [200, 204]:
                print(f"[DELETE] ✓ Deleted from NAMED graph <http://www.transport-ontology.org/travel>")
                deleted_count += 1
            else:
                print(f"[DELETE] Named graph delete returned: {resp.status_code}")
        except Exception as e:
            print(f"[DELETE] Named graph error: {e}")
    
    if deleted_count > 0:
        print(f"\n[DELETE] ✓✓✓ Successfully deleted from {deleted_count} location(s)")
        import time
        time.sleep(0.5)
        return True
    else:
        print(f"\n[DELETE] ✗✗✗ No instances were deleted")
        return False  

def update_company(old_name, new_data):
    delete_company(old_name)
    return create_company(new_data)




def cleanup_company_duplicates(name: str):
    """Keep preferred :company_<Name> and delete other subjects having the same :companyName."""
    preferred = f":company_{name.replace(' ', '_')}"
    q = f'SELECT ?s WHERE {{ ?s :companyName "{escape_sparql_string(name)}" }}'
    res = query_all_graphs(q)
    for b in res.get('results', {}).get('bindings', []):
        s = b.get('s', {}).get('value')
        if not s or s.endswith(preferred.replace(':', NS)):
            continue
        _delete_node_everywhere(f"<{s}>")


def _delete_node_everywhere(node: str):
    """Delete triples for node from all graphs"""
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    # Delete from default graph
    try:
        payload = {'update': SPARQL_PREFIXES + f"DELETE WHERE {{ {node} ?p ?o }}"}
        requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=15)
    except:
        pass
    
    # Delete from named graph
    try:
        payload = {'update': SPARQL_PREFIXES + f"WITH <{GRAPH_URI}> DELETE WHERE {{ {node} ?p ?o }}"}
        requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=15)
    except:
        pass