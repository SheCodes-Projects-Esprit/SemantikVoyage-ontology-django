# city/utils/ontology_manager.py
import time
from rdflib import Graph
from SPARQLWrapper import SPARQLWrapper, JSON, POST, URLENCODED
import requests

SPARQL_PREFIXES = """
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

NS = "http://www.transport-ontology.org/travel#"
FUSEKI_QUERY_URL = "http://localhost:3030/transport_db/query"
FUSEKI_UPDATE_URL = "http://localhost:3030/transport_db/update"


def _run_query(query: str):
    sw = SPARQLWrapper(FUSEKI_QUERY_URL)
    sw.setReturnFormat(JSON)
    sw.setMethod('POST')
    sw.setRequestMethod(URLENCODED)
    sw.setQuery(SPARQL_PREFIXES + query)
    return sw.query().convert()


def _run_query_all_graphs(query: str):
    """Execute a SPARQL SELECT across ALL graphs (no default-graph-uri).
    This mimics Fuseki UI behavior and ensures we see triples inserted into a named graph.
    """
    try:
        headers = {'Accept': 'application/sparql-results+json'}
        resp = requests.get(FUSEKI_QUERY_URL, params={'query': SPARQL_PREFIXES + query}, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[city/_run_query_all_graphs] HTTP query failed: {e}")
        return {"results": {"bindings": []}}


def query_all_graphs(sparql: str):
    """Public helper: run SELECT across ALL graphs (no default-graph-uri)."""
    return _run_query_all_graphs(sparql)


def _resolve_city_subject_by_name(city_name: str):
    sname = escape_sparql_string(city_name)
    q = f"""
    SELECT ?s WHERE {{ ?s :cityName "{sname}" }} LIMIT 1
    """
    res = _run_query_all_graphs(q)
    bindings = res.get('results', {}).get('bindings', [])
    if not bindings:
        return None
    return f"<{bindings[0].get('s', {}).get('value', '')}>" if bindings[0].get('s') else None


def _delete_node_everywhere(node: str):
    """Delete triples for node as subject or object across default and named graphs."""
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    graph_uri = NS.rstrip('#')

    # 1) Default graph deletes
    try:
        requests.post(FUSEKI_UPDATE_URL, data={'update': f"DELETE WHERE {{ {node} ?p ?o }}"}, headers=headers, timeout=15)
        requests.post(FUSEKI_UPDATE_URL, data={'update': f"DELETE WHERE {{ ?s ?p {node} }}"}, headers=headers, timeout=15)
    except Exception:
        pass

    # 2) Specific ontology named graph
    try:
        requests.post(FUSEKI_UPDATE_URL, data={'update': f"WITH <{graph_uri}> DELETE WHERE {{ {node} ?p ?o }}"}, headers=headers, timeout=15)
        requests.post(FUSEKI_UPDATE_URL, data={'update': f"WITH <{graph_uri}> DELETE WHERE {{ ?s ?p {node} }}"}, headers=headers, timeout=15)
    except Exception:
        pass

    # 3) Any named graph
    try:
        upd1 = f"DELETE {{ GRAPH ?g {{ {node} ?p ?o }} }} WHERE {{ GRAPH ?g {{ {node} ?p ?o }} }}"
        upd2 = f"DELETE {{ GRAPH ?g {{ ?s ?p {node} }} }} WHERE {{ GRAPH ?g {{ ?s ?p {node} }} }}"
        requests.post(FUSEKI_UPDATE_URL, data={'update': upd1}, headers=headers, timeout=15)
        requests.post(FUSEKI_UPDATE_URL, data={'update': upd2}, headers=headers, timeout=15)
    except Exception:
        pass


def cleanup_city_duplicates(name: str):
    """Keep preferred :city_<Name> and delete other subjects having the same :cityName."""
    preferred = f":city_{name.replace(' ', '_')}"
    q = f"""
    SELECT ?s WHERE {{ ?s :cityName "{escape_sparql_string(name)}" }}
    """
    res = _run_query_all_graphs(q)
    for b in res.get('results', {}).get('bindings', []):
        s = b.get('s', {}).get('value')
        if not s:
            continue
        # skip preferred if matches local name
        if s.endswith(preferred.replace(':', NS)) or s.endswith(preferred.split(':')[1]):
            continue
        _delete_node_everywhere(f"<{s}>")


def delete_city_by_name(name: str) -> bool:
    """Delete ALL subjects that have :cityName matching name (with and without artifacts)."""
    norm = escape_sparql_string(name)
    alt = escape_sparql_string(f"with name {name}")
    q = f"""
    SELECT ?s WHERE {{
      {{ ?s :cityName "{norm}" }} UNION {{ ?s :cityName "{alt}" }}
    }}
    """
    res = _run_query_all_graphs(q)
    any_deleted = False
    for b in res.get('results', {}).get('bindings', []):
        s = b.get('s', {}).get('value')
        if s:
            _delete_node_everywhere(f"<{s}>")
            any_deleted = True
    # Also attempt canonical URI
    _delete_node_everywhere(f":city_{name.replace(' ', '_')}")
    _delete_node_everywhere(f":city_with_name_{name.replace(' ', '_')}")
    return any_deleted


def _run_update(update: str):
    sw = SPARQLWrapper(FUSEKI_UPDATE_URL)
    sw.setMethod(POST)
    sw.setRequestMethod(URLENCODED)
    sw.setQuery(SPARQL_PREFIXES + update)
    sw.query()


def city_sparql_update(update: str):
    """City-scoped SPARQL UPDATE that guarantees using the ontology named graph.
    This does NOT touch shared utils; it's only used by the City app.
    Rules:
      - INSERT DATA -> INSERT DATA { GRAPH <http://www.transport-ontology.org/travel> { ... } }
      - DELETE WHERE -> WITH <graph>\nDELETE WHERE { ... }
      - DELETE/INSERT (MODIFY) -> WITH <graph>\n<original>
    """
    graph_uri = "http://www.transport-ontology.org/travel"
    text = update or ""
    # Normalize small known typos from the LLM (ensure INSERT uses correct predicate)
    text = text.replace('City_hasName', 'cityName').replace(':City_hasName', ':cityName')

    upper = text.upper()
    payload = None
    if 'INSERT DATA' in upper:
        # If a GRAPH clause already exists inside INSERT, do NOT inject another one
        try:
            import re
            has_graph = re.search(r'INSERT\s+DATA\s*{[^}]*GRAPH\s*<', text, flags=re.IGNORECASE | re.DOTALL) is not None
            if not has_graph:
                # Inject GRAPH into the opening INSERT DATA
                text = re.sub(r'INSERT\s+DATA\s*{', f'INSERT DATA {{ GRAPH <{graph_uri}> {{', text, count=1, flags=re.IGNORECASE)
                # Ensure an extra closing brace to close the GRAPH block
                text = text.rstrip()
                if text.endswith('}'):  # closes inner block
                    text = text + '}'   # close outer INSERT
                else:
                    text = text + ' }}'
        except Exception:
            pass
        payload = {'update': SPARQL_PREFIXES + '\n' + text}
    elif 'DELETE WHERE' in upper:
        try:
            import re
            text = re.sub(r'DELETE\s+WHERE', f'WITH <{graph_uri}>\nDELETE WHERE', text, count=1, flags=re.IGNORECASE)
        except Exception:
            pass
        payload = {'update': SPARQL_PREFIXES + text}
    elif upper.strip().startswith('DELETE') and 'INSERT' in upper:
        text = f"WITH <{graph_uri}>\n{text}"
        payload = {'update': SPARQL_PREFIXES + text}
    else:
        payload = {'update': SPARQL_PREFIXES + text}

    try:
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp = requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=20)
        if resp.status_code != 200:
            raise Exception(f"Fuseki update failed: {resp.status_code} - {resp.text}")
        # Post-fix: migrate any :City_hasName literals to :cityName and remove old ones
        fix_insert = f"""
        PREFIX : <{NS}>
        INSERT {{ GRAPH <{graph_uri}> {{ ?s :cityName ?n }} }}
        WHERE  {{ GRAPH <{graph_uri}> {{ ?s :City_hasName ?n }} }}
        """
        requests.post(FUSEKI_UPDATE_URL, data={'update': fix_insert}, headers=headers, timeout=20)
        fix_delete = f"""
        PREFIX : <{NS}>
        WITH <{graph_uri}>
        DELETE WHERE {{ {{ ?s :City_hasName ?n }} }}
        """
        requests.post(FUSEKI_UPDATE_URL, data={'update': fix_delete}, headers=headers, timeout=20)
        return True
    except Exception as e:
        print(f"[city_sparql_update] Error: {e}")
        raise

def escape_sparql_string(value):
    if value is None: return ""
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def create_city(data, city_type):
    city_name = data.get('name', '').strip()
    if not city_name:
        raise ValueError("City name is required!")

    uri = f":city_{city_name.replace(' ', '_')}"

    triples = f"""
    {uri} a :{city_type}City ;
          :cityName "{escape_sparql_string(city_name)}"
    """

    if data.get('population'):
        triples += f" ;\n          :population {int(data['population'])}"
    if data.get('area_km2'):
        triples += f" ;\n          :area {float(data['area_km2']):.2f}"

    # Type-specific
    if city_type == 'Capital':
        triples += f" ;\n          :governmentSeat {str(data.get('government_seat', False)).lower()}"
        if data.get('ministries') is not None:
            triples += f" ;\n          :numberOfMinistries {int(data['ministries'])}"
    elif city_type == 'Metropolitan':
        if data.get('districts') is not None:
            triples += f" ;\n          :numberOfDistricts {int(data['districts'])}"
        if data.get('commute_minutes') is not None:
            triples += f" ;\n          :averageCommuteTime {float(data['commute_minutes']):.1f}"
    elif city_type == 'Touristic':
        if data.get('annual_visitors') is not None:
            triples += f" ;\n          :annualVisitors {int(data['annual_visitors'])}"
        if data.get('hotels') is not None:
            triples += f" ;\n          :hotelCount {int(data['hotels'])}"
    elif city_type == 'Industrial':
        if data.get('factories') is not None:
            triples += f" ;\n          :numberOfFactories {int(data['factories'])}"
        if data.get('pollution_index') is not None:
            triples += f" ;\n          :pollutionIndex {float(data['pollution_index']):.1f}"

    triples += " ."

    sparql = f"INSERT DATA {{ {triples} }}"
    _run_update(sparql)
    time.sleep(0.2)
    return city_name

def get_city(city_name):
    uri = f":city_{city_name.replace(' ', '_')}"
    q = f"""
    SELECT ?prop ?val WHERE {{
      {uri} ?prop ?val .
      FILTER(isIRI(?val) || isLiteral(?val))
    }}
    """
    results = _run_query(q)
    rows = [(b['prop']['value'], b['val']['value']) for b in results.get('results', {}).get('bindings', [])]
    if not rows:
            # Try search across all graphs
        results = _run_query_all_graphs(q)
        rows = [(b['prop']['value'], b['val']['value']) for b in results.get('results', {}).get('bindings', [])]
        if not rows:
            # Resolve by name to arbitrary subject, then re-query
            node = _resolve_city_subject_by_name(city_name)
            if node:
                q2 = f"""
                SELECT ?prop ?val WHERE {{
                  {node} ?prop ?val .
                  FILTER(isIRI(?val) || isLiteral(?val))
                }}
                """
                results = _run_query_all_graphs(q2)
                rows = [(b['prop']['value'], b['val']['value']) for b in results.get('results', {}).get('bindings', [])]
            if not rows:
                return None

    data = {'name': city_name}
    city_type = 'Capital'

    for prop_term, val_term in rows:
        prop = str(prop_term).split('#')[-1]
        val = str(val_term)
        if prop == 'type':
            if 'CapitalCity' in val: city_type = 'Capital'
            elif 'MetropolitanCity' in val: city_type = 'Metropolitan'
            elif 'TouristicCity' in val: city_type = 'Touristic'
            elif 'IndustrialCity' in val: city_type = 'Industrial'
        else:
            # Normalize RDF property names to form/template field names
            if prop == 'area':
                data['area_km2'] = val
            elif prop == 'governmentSeat':
                data['government_seat'] = (val.lower() == 'true')
            elif prop == 'numberOfMinistries':
                data['ministries'] = val
            elif prop == 'numberOfDistricts':
                data['districts'] = val
            elif prop == 'annualVisitors':
                data['annual_visitors'] = val
            elif prop == 'numberOfFactories':
                data['factories'] = val
            elif prop == 'pollutionIndex':
                data['pollution_index'] = val
            elif prop == 'hotelCount':
                data['hotels'] = val
            elif prop == 'averageCommuteTime':
                data['commute_minutes'] = val
            elif prop == 'cityName':
                data['name'] = val
            else:
                data[prop] = val

    data['type'] = city_type
    return data

def list_cities():
    q = """
    SELECT ?name ?pop ?area ?type ?region
           ?ministries ?districts ?visitors ?factories ?pollution ?hotels ?commute
    WHERE {
      ?s rdf:type/rdfs:subClassOf* :City .
      ?s :cityName ?name .
      OPTIONAL { ?s :population ?pop }
      OPTIONAL { ?s :area ?area }
      OPTIONAL { ?s :region ?region }
      OPTIONAL { ?s rdf:type ?type }
      OPTIONAL { ?s :numberOfMinistries ?ministries }
      OPTIONAL { ?s :numberOfDistricts ?districts }
      OPTIONAL { ?s :annualVisitors ?visitors }
      OPTIONAL { ?s :numberOfFactories ?factories }
      OPTIONAL { ?s :pollutionIndex ?pollution }
      OPTIONAL { ?s :hotelCount ?hotels }
      OPTIONAL { ?s :averageCommuteTime ?commute }
    }
    ORDER BY ?name
    """
    # Search across all graphs to include AI-inserted triples
    results = _run_query_all_graphs(q)
    rows = []
    for b in results.get('results', {}).get('bindings', []):
        name = b['name']['value']
        pop = b.get('pop', {}).get('value')
        area = b.get('area', {}).get('value')
        t = b.get('type', {}).get('value', '')
        region = b.get('region', {}).get('value')
        ministries = b.get('ministries', {}).get('value')
        districts = b.get('districts', {}).get('value')
        visitors = b.get('visitors', {}).get('value')
        factories = b.get('factories', {}).get('value')
        pollution = b.get('pollution', {}).get('value')
        hotels = b.get('hotels', {}).get('value')
        commute = b.get('commute', {}).get('value')
        city_type = 'Unknown'
        if 'CapitalCity' in t: city_type = 'Capital'
        elif 'MetropolitanCity' in t: city_type = 'Metropolitan'
        elif 'TouristicCity' in t: city_type = 'Touristic'
        elif 'IndustrialCity' in t: city_type = 'Industrial'

        rows.append({
            "name": name,
            "population": pop if pop is not None else 0,
            "area": area if area is not None else 0.0,
            "region": region if region is not None else '',
            "type": city_type,
            "numberOfMinistries": ministries,
            "numberOfDistricts": districts,
            "annualVisitors": visitors,
            "numberOfFactories": factories,
            "pollutionIndex": pollution,
            "hotelCount": hotels,
            "averageCommuteTime": commute,
        })
    return rows

def update_city(old_name, new_data):
    delete_city(old_name)
    return create_city(new_data, new_data.get("type", "Capital"))

def delete_city(city_name):
    uri = f":city_{city_name.replace(' ', '_')}"
    try:
        _run_update(f"DELETE WHERE {{ {uri} ?p ?o }}")
        return True
    except Exception:
        return False