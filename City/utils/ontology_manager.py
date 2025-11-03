# city/utils/ontology_manager.py
import time
import traceback
from django.conf import settings
from core.utils.fuseki import sparql_query, sparql_update
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

def _run_sparql(query, timeout=10):
    try:
        headers = {'Accept': 'application/sparql-results+json'}
        resp = requests.get(FUSEKI_QUERY_URL, params={'query': query}, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"_run_sparql failed: {e}")
        return {}

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
          :cityName "{escape_sparql_string(city_name)}" ;
          :overallStatus "{escape_sparql_string(data.get('overall_status', 'Planned'))}"
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

    sparql = f"PREFIX : <{NS}> INSERT DATA {{ {triples} }}"

    try:
        sparql_update(sparql)
        time.sleep(0.5)
        return city_name
    except Exception as e:
        raise Exception(f"SPARQL Error: {e}")

def get_city(city_name):
    uri = f":city_{city_name.replace(' ', '_')}"
    query = SPARQL_PREFIXES + f"""
    SELECT ?prop ?val WHERE {{ {uri} ?prop ?val . }}
    """
    result = _run_sparql(query)
    bindings = result.get('results', {}).get('bindings', [])
    if not bindings: return None

    data = {'name': city_name}
    city_type = 'Capital'

    for b in bindings:
        prop = b['prop']['value'].split('#')[-1]
        val = b['val']['value']
        if prop == 'type':
            if 'CapitalCity' in val: city_type = 'Capital'
            elif 'MetropolitanCity' in val: city_type = 'Metropolitan'
            elif 'TouristicCity' in val: city_type = 'Touristic'
            elif 'IndustrialCity' in val: city_type = 'Industrial'
        else:
            # Normalize RDF property names to form/template field names
            if prop == 'overallStatus':
                data['overall_status'] = val
            elif prop == 'area':
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
    data.setdefault('overall_status', 'Active')
    return data

def list_cities():
    query = SPARQL_PREFIXES + """
    SELECT ?s ?name ?status ?pop ?area ?type ?region
           ?ministries ?districts ?visitors ?factories ?pollution ?hotels ?commute
    WHERE {
      ?s rdf:type/rdfs:subClassOf* :City .
      ?s :cityName ?name .
      OPTIONAL { ?s :overallStatus ?status }
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
    result = _run_sparql(query)
    rows = []
    for b in result.get('results', {}).get('bindings', []):
        name = b['name']['value']
        t = b.get('type', {}).get('value', '')
        city_type = 'Unknown'
        if 'CapitalCity' in t: city_type = 'Capital'
        elif 'MetropolitanCity' in t: city_type = 'Metropolitan'
        elif 'TouristicCity' in t: city_type = 'Touristic'
        elif 'IndustrialCity' in t: city_type = 'Industrial'

        rows.append({
            "name": name,
            "status": b.get('status', {}).get('value', 'Active'),
            "population": b.get('pop', {}).get('value', 0),
            "area": b.get('area', {}).get('value', 0.0),
            "region": b.get('region', {}).get('value', ''),
            "type": city_type,
            "numberOfMinistries": b.get('ministries', {}).get('value'),
            "numberOfDistricts": b.get('districts', {}).get('value'),
            "annualVisitors": b.get('visitors', {}).get('value'),
            "numberOfFactories": b.get('factories', {}).get('value'),
            "pollutionIndex": b.get('pollution', {}).get('value'),
            "hotelCount": b.get('hotels', {}).get('value'),
            "averageCommuteTime": b.get('commute', {}).get('value'),
        })
    return rows

def update_city(old_name, new_data):
    delete_city(old_name)
    return create_city(new_data, new_data.get("type", "Capital"))

def delete_city(city_name):
    uri = f":city_{city_name.replace(' ', '_')}"
    sparql = f"PREFIX : <{NS}> DELETE WHERE {{ {uri} ?p ?o }}"
    try:
        sparql_update(sparql)
        return True
    except:
        return False