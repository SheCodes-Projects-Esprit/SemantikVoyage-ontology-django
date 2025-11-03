import time
from rdflib.plugins.stores.sparqlstore import SPARQLStore, SPARQLUpdateStore
from rdflib import Graph


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


def _run_update(update: str):
    store = SPARQLUpdateStore()
    store.open((FUSEKI_QUERY_URL, FUSEKI_UPDATE_URL))
    try:
        store.update(SPARQL_PREFIXES + update)
    finally:
        try:
            store.close()
        except Exception:
            pass


def escape_sparql_string(value):
    if value is None:
        return ""
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def _resolve_company_subject_by_name(name: str):
    """Return a SPARQL node for the company resource that has :companyName name.
    Prefer absolute angle-bracket URI to be safe in updates.
    """
    sname = escape_sparql_string(name)
    q = f"""
    SELECT ?s ?type WHERE {{
      ?s :companyName "{sname}" .
      OPTIONAL {{ ?s rdf:type ?type }}
    }} LIMIT 1
    """
    res = _run_query(q)
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
    triples = f"""
    {uri} a :{company_type} ;
          :companyName "{escape_sparql_string(name)}"
    """

    # Common properties in ontology
    if data.get('number_of_employees') not in (None, ""):
        try:
            triples += f" ;\n          :numberOfEmployees {int(data['number_of_employees'])}"
        except (ValueError, TypeError):
            pass
    if data.get('founded_year'):
        triples += f" ;\n          :foundedYear \"{escape_sparql_string(data['founded_year'])}\""
    if data.get('headquarters_location'):
        triples += f" ;\n          :headquartersLocation \"{escape_sparql_string(data['headquarters_location'])}\""

    # Subclass specific
    if company_type == 'BusCompany':
        if data.get('number_of_bus_lines') not in (None, ""):
            triples += f" ;\n          :numberOfBusLines {int(data['number_of_bus_lines'])}"
        if data.get('average_bus_age') not in (None, ""):
            triples += f" ;\n          :averageBusAge {float(data['average_bus_age']):.1f}"
        if data.get('ticket_price') not in (None, ""):
            triples += f" ;\n          :ticketPrice {float(data['ticket_price']):.2f}"
        if str(data.get('eco_friendly_fleet', '')).lower() in ['true', 'false']:
            triples += f" ;\n          :ecoFriendlyFleet {str(data['eco_friendly_fleet']).lower()}"
    elif company_type == 'MetroCompany':
        if data.get('number_of_lines') not in (None, ""):
            triples += f" ;\n          :numberOfLines {int(data['number_of_lines'])}"
        if data.get('total_track_length') not in (None, ""):
            triples += f" ;\n          :totalTrackLength {float(data['total_track_length']):.1f}"
        if data.get('automation_level'):
            triples += f" ;\n          :automationLevel \"{escape_sparql_string(data['automation_level'])}\""
        if data.get('daily_passengers') not in (None, ""):
            triples += f" ;\n          :dailyPassengers {int(data['daily_passengers'])}"
    elif company_type == 'TaxiCompany':
        if data.get('number_of_vehicles') not in (None, ""):
            triples += f" ;\n          :numberOfVehicles {int(data['number_of_vehicles'])}"
        if str(data.get('booking_app', '')).lower() in ['true', 'false']:
            triples += f" ;\n          :bookingApp {str(data['booking_app']).lower()}"
        if data.get('average_fare_per_km') not in (None, ""):
            triples += f" ;\n          :averageFarePerKm {float(data['average_fare_per_km']):.2f}"
    elif company_type == 'BikeSharingCompany':
        if data.get('number_of_stations') not in (None, ""):
            triples += f" ;\n          :numberOfStations {int(data['number_of_stations'])}"
        if data.get('bike_count') not in (None, ""):
            triples += f" ;\n          :bikeCount {int(data['bike_count'])}"
        if data.get('subscription_price') not in (None, ""):
            triples += f" ;\n          :subscriptionPrice {float(data['subscription_price']):.2f}"
        if str(data.get('electric_bikes', '')).lower() in ['true', 'false']:
            triples += f" ;\n          :electricBikes {str(data['electric_bikes']).lower()}"

    triples += " ."

    sparql = f"INSERT DATA {{ {triples} }}"
    _run_update(sparql)
    time.sleep(0.2)
    return name


def get_company(name):
    # Try synthetic URI first
    uri = f":company_{str(name).replace(' ', '_')}"
    q_direct = f"""
    SELECT ?prop ?val WHERE {{
      {uri} ?prop ?val .
      FILTER(isIRI(?val) || isLiteral(?val))
    }}
    """
    results = _run_query(q_direct)
    rows = [(b['prop']['value'], b['val']['value']) for b in results.get('results', {}).get('bindings', [])]
    # Fallback: resolve by companyName in ontology
    used_node = uri
    if not rows:
        node, t_val = _resolve_company_subject_by_name(name)
        if not node:
            return None
        used_node = node
        q_byname = f"""
        SELECT ?prop ?val WHERE {{
          {node} ?prop ?val .
          FILTER(isIRI(?val) || isLiteral(?val))
        }}
        """
        results = _run_query(q_byname)
        rows = [(b['prop']['value'], b['val']['value']) for b in results.get('results', {}).get('bindings', [])]

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
        elif prop == 'bookingApp':
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
    q = """
    SELECT ?name ?type ?employees ?year ?hq ?busLines ?metroLines ?vehicles ?stations WHERE {
      ?s rdf:type/rdfs:subClassOf* :Company .
      OPTIONAL { ?s :companyName ?name }
      OPTIONAL { ?s rdf:type ?type }
      OPTIONAL { ?s :numberOfEmployees ?employees }
      OPTIONAL { ?s :foundedYear ?year }
      OPTIONAL { ?s :headquartersLocation ?hq }
      OPTIONAL { ?s :numberOfBusLines ?busLines }
      OPTIONAL { ?s :numberOfLines ?metroLines }
      OPTIONAL { ?s :numberOfVehicles ?vehicles }
      OPTIONAL { ?s :numberOfStations ?stations }
    }
    ORDER BY ?name
    """
    results = _run_query(q)
    rows = []
    for b in results.get('results', {}).get('bindings', []):
        t = b.get('type', {}).get('value', '')
        ctype = 'Company'
        if 'BusCompany' in t: ctype = 'Bus'
        elif 'MetroCompany' in t: ctype = 'Metro'
        elif 'TaxiCompany' in t: ctype = 'Taxi'
        elif 'BikeSharingCompany' in t: ctype = 'BikeSharing'
        rows.append({
            "name": b.get('name', {}).get('value', ''),
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


def update_company(old_name, new_data):
    delete_company(old_name)
    return create_company(new_data)


def delete_company(name):
    # Try both synthetic URI and resolved subject
    candidates = []
    candidates.append(f":company_{str(name).replace(' ', '_')}")
    node, _ = _resolve_company_subject_by_name(name)
    if node:
        candidates.append(node)
    ok = False
    for node in candidates:
        try:
            _run_update(f"DELETE WHERE {{ {node} ?p ?o }}")
            ok = True
        except Exception:
            pass
    return ok

