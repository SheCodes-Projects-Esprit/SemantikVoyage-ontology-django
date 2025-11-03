# company/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import BusCompanyForm, MetroCompanyForm, TaxiCompanyForm, BikeSharingCompanyForm
from .utils.ontology_manager import (
    create_company, get_company, update_company, delete_company, list_companies,
    query_all_graphs, cleanup_company_duplicates, _run_update  # ← FIXED
)
from .utils.nl_to_sparql_company import company_nl_to_sparql, company_nl_to_sparql_update
import re


def company_list(request):
    companies = list_companies()
    return render(request, "core/company/company_list.html", {"companies": companies})


# Replace the company_ai_query function in company/views.py

def company_ai_query(request):
    if request.method != 'POST':
        return redirect('company:list')

    user_text = (request.POST.get('q') or '').strip()
    if not user_text:
        messages.error(request, 'Please enter a command.')
        return redirect('company:list')

    lower = user_text.lower()
    is_update = any(k in lower for k in ['add ', 'create', 'insert', 'delete', 'remove', 'update', 'modify', 'change'])

    try:
        import re
        
        # === UPDATE MODE ===
        if is_update:
            # Deterministic ADD handler: "Add <type> company <name>"
            added = False
            generated_sparql = ""
            
            m = re.search(r"add\s+(bus|metro|taxi|bikesharing|bike\s*sharing)?\s*company\s+([\w\-\s]+)", user_text, flags=re.IGNORECASE)
            if m:
                tword = (m.group(1) or '').strip().lower().replace(' ', '')
                name_val = m.group(2).strip()
                type_map = {
                    'bus': 'BusCompany',
                    'metro': 'MetroCompany',
                    'taxi': 'TaxiCompany',
                    'bikesharing': 'BikeSharingCompany',
                }
                subclass = type_map.get(tword, 'Company')
                
                # Build the SPARQL for display
                uri = f":company_{name_val.replace(' ', '_')}"
                triples = f'{uri} a :{subclass} ;\n  :companyName "{name_val}" .'
                generated_sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

INSERT DATA {{
  GRAPH <http://www.transport-ontology.org/travel> {{
    {triples}
  }}
}}"""
                
                # Use existing create_company util for reliability
                try:
                    create_company({'name': name_val, 'type': subclass})
                    cleanup_company_duplicates(name_val)
                    messages.success(request, f"Company '{name_val}' added!")
                    added = True
                except Exception as e:
                    print(f"[DEBUG] create_company failed: {e}, trying direct SPARQL")
                    # Fallback to direct SPARQL
                    from .utils.ontology_manager import company_sparql_update
                    company_sparql_update(triples)
                    cleanup_company_duplicates(name_val)
                    messages.success(request, f"Company '{name_val}' added!")
                    added = True
            
            # Deterministic DELETE handler - multiple patterns
            if not added:
                # Pattern 1: "Delete SOTRA" or "Delete company SOTRA"
                mdel1 = re.search(r"delete\s+(?:company\s+)?([a-zA-Z0-9\-\s]+)$", user_text, flags=re.IGNORECASE)
                # Pattern 2: "Delete company where name = SOTRA"
                mdel2 = re.search(r"delete\s+company\s+where\s+name\s*=\s*['\"]?([a-zA-Z0-9\-\s]+)['\"]?", user_text, flags=re.IGNORECASE)
                
                target_name = None
                if mdel2:
                    target_name = mdel2.group(1).strip()
                elif mdel1:
                    candidate = mdel1.group(1).strip()
                    # Avoid matching command words
                    if candidate.lower() not in ['company', 'where', 'name', 'from']:
                        target_name = candidate
                
                if target_name:
                    generated_sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

# Delete from default graph
DELETE WHERE {{
  :company_{target_name.replace(' ', '_')} ?p ?o
}}

# Delete from named graph
WITH <http://www.transport-ontology.org/travel>
DELETE WHERE {{
  :company_{target_name.replace(' ', '_')} ?p ?o
}}"""
                    
                    if delete_company(target_name):
                        messages.success(request, f"Company '{target_name}' deleted!")
                    else:
                        messages.warning(request, f"No company named '{target_name}' found.")
                    
                    # Show result with SPARQL
                    import time
                    time.sleep(0.3)  # Brief pause for Fuseki to sync
                    companies = list_companies()
                    return render(request, 'core/company/company_list.html', {
                        'companies': companies,
                        'ai_query': user_text,
                        'ai_sparql': generated_sparql,
                        'ai_message': f"Deleted '{target_name}'"
                    })
                    added = True  # Mark as handled
            
            # Fallback: use AI-generated SPARQL
            if not added:
                sparql = company_nl_to_sparql_update(user_text)
                if sparql:
                    # Check if this is a DELETE operation
                    if any(kw in lower for kw in ['delete', 'remove']):
                        # Extract company name from pattern like ":company_X ?p ?o"
                        import re
                        match = re.search(r':company_(\w+)', sparql)
                        if match:
                            name = match.group(1).replace('_', ' ')
                            if delete_company(name):
                                generated_sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>

# Delete from default graph
DELETE WHERE {{ {sparql} }}

# Delete from named graph  
WITH <http://www.transport-ontology.org/travel>
DELETE WHERE {{ {sparql} }}"""
                                messages.success(request, f"Company '{name}' deleted!")
                            else:
                                messages.warning(request, f"No company named '{name}' found.")
                        else:
                            messages.error(request, 'Could not parse company name from DELETE command.')
                            return redirect('company:list')
                    else:
                        # INSERT operation
                        from .utils.ontology_manager import company_sparql_update
                        company_sparql_update(sparql)
                        generated_sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

INSERT DATA {{
  GRAPH <http://www.transport-ontology.org/travel> {{
    {sparql}
  }}
}}"""
                        messages.success(request, 'Company updated via AI!')
                else:
                    messages.error(request, 'Could not generate SPARQL.')
                    return redirect('company:list')
            
            # Force refresh and return with SPARQL displayed
            import time
            time.sleep(0.3)  # Brief pause for Fuseki to sync
            companies = list_companies()
            return render(request, 'core/company/company_list.html', {
                'companies': companies,
                'ai_query': user_text,
                'ai_sparql': generated_sparql,
                'ai_message': 'Update executed!'
            })

        # === QUERY MODE ===
        else:
            # Fast path: name lookup for queries
            name_match = re.search(r"name\s*=\s*['\"]?([\w\-\s]+)['\"]?", user_text, re.IGNORECASE)
            if name_match:
                target = name_match.group(1).strip()
                sparql = f"""
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?employees ?hq ?type
WHERE {{
  ?c a/rdfs:subClassOf* :Company ; :companyName ?name .
  FILTER(LCASE(?name) = "{target.lower()}")
  OPTIONAL {{ ?c :numberOfEmployees ?employees }}
  OPTIONAL {{ ?c :headquartersLocation ?hq }}
  OPTIONAL {{ ?c rdf:type ?type }}
}} LIMIT 10
"""
            else:
                sparql = company_nl_to_sparql(user_text)

            if not sparql:
                messages.error(request, 'Could not generate SPARQL.')
                return redirect('company:list')

            data = query_all_graphs(sparql)
            bindings = data.get('results', {}).get('bindings', [])
            
            if not bindings:
                messages.warning(request, "No results found.")
                return redirect('company:list')

            vars_ = list(bindings[0].keys())
            rows = []
            for b in bindings:
                row = {}
                for v in vars_:
                    val = b.get(v, {}).get('value', '')
                    key = v
                    # Normalize keys for display
                    if v in ['employees', 'numberOfEmployees']: key = 'employees'
                    elif v in ['year', 'foundedYear']: key = 'year'
                    elif v in ['hq', 'headquartersLocation']: key = 'hq'
                    elif v in ['vehicles', 'numberOfVehicles']: key = 'vehicles'
                    elif v in ['fare', 'averageFarePerKm']: key = 'fare'
                    elif v in ['busLines', 'numberOfBusLines']: key = 'busLines'
                    elif v in ['metroLines', 'numberOfLines']: key = 'metroLines'
                    elif v in ['stations', 'numberOfStations']: key = 'stations'
                    elif v in ['bikes', 'totalBikes', 'bikeCount']: key = 'bikes'
                    elif v in ['name', 'companyName']: key = 'name'
                    elif v == 'type': key = 'type'
                    row[key] = val
                rows.append(row)

            # Get full company details
            selected_names = [r.get('name') for r in rows if r.get('name')]
            companies = []
            for name in selected_names:
                c = get_company(name)
                if c:
                    # Normalize for template
                    c['employees'] = c.get('number_of_employees')
                    c['year'] = c.get('founded_year')
                    c['hq'] = c.get('headquarters_location')
                    c['vehicles'] = c.get('number_of_vehicles')
                    c['fare'] = c.get('average_fare_per_km')
                    c['busLines'] = c.get('number_of_bus_lines')
                    c['metroLines'] = c.get('number_of_lines')
                    c['stations'] = c.get('number_of_stations')
                    c['bikes'] = c.get('bike_count')
                    c['type'] = c.get('type', 'Company').replace('Company', '')
                    companies.append(c)

            return render(request, 'core/company/company_list.html', {
                'companies': companies,
                'ai_query': user_text,
                'ai_sparql': sparql,
                'ai_results': bindings,
                'ai_table_vars': vars_,
                'ai_table_rows': rows,
            })

    except Exception as e:
        import traceback
        print(f"[ERROR] {e}")
        print(traceback.format_exc())
        messages.error(request, f"AI Error: {e}")
        return redirect('company:list')
        
# ——— CRUD VIEWS (UNCHANGED) ———
def company_detail(request, name):
    company = get_company(name)
    if not company:
        messages.error(request, f"Company '{name}' not found.")
        return redirect("company:list")
    return render(request, "core/company/company_detail.html", {"company": company})


def company_create(request):
    type_ = request.GET.get("type", "Bus").strip()
    type_map = {
        "Bus": ("BusCompany", BusCompanyForm),
        "Metro": ("MetroCompany", MetroCompanyForm),
        "Taxi": ("TaxiCompany", TaxiCompanyForm),
        "BikeSharing": ("BikeSharingCompany", BikeSharingCompanyForm),
    }
    company_type, Form = type_map.get(type_.title() if type_.lower() != 'bikesharing' else 'BikeSharing', ("BusCompany", BusCompanyForm))

    if request.method == "POST":
        form = Form(request.POST)
        if form.is_valid():
            data = {**form.cleaned_data, "type": company_type}
            try:
                created_name = create_company(data)
                messages.success(request, f"Company '{created_name}' created!")
                return redirect("company:detail", name=created_name)
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = Form()
    return render(request, "core/company/company_form.html", {"form": form, "is_update": False, "type": company_type})


def company_update(request, name):
    company = get_company(name)
    if not company:
        messages.error(request, "Company not found.")
        return redirect("company:list")

    type_map = {
        "BusCompany": BusCompanyForm,
        "MetroCompany": MetroCompanyForm,
        "TaxiCompany": TaxiCompanyForm,
        "BikeSharingCompany": BikeSharingCompanyForm,
    }
    Form = type_map.get(company.get("type"), BusCompanyForm)

    if request.method == "POST":
        form = Form(request.POST, original_name=name)
        if form.is_valid():
            data = {**form.cleaned_data, "type": company.get("type", "Company")}
            try:
                update_company(name, data)
                messages.success(request, f"Company '{data['name']}' updated!")
                return redirect("company:detail", name=data['name'])
            except Exception as e:
                messages.error(request, str(e))
    else:
        init = {k: company.get(k) for k in Form.Meta.fields}
        form = Form(initial=init, original_name=name)

    return render(request, "core/company/company_form.html", {"form": form, "name": name, "is_update": True, "type": company.get("type")})


def company_delete(request, name):
    if request.method == "POST":
        if delete_company(name):
            messages.success(request, f"Company '{name}' deleted!")
        else:
            messages.error(request, "Delete failed.")
        return redirect("company:list")
    company = get_company(name)
    return render(request, "core/company/company_delete_confirm.html", {"company": company, "name": name})

# Add this to company/views.py temporarily for debugging

def company_debug(request):
    """Debug view to see what's in each graph"""
    from .utils.ontology_manager import query_all_graphs, SPARQL_PREFIXES, FUSEKI_QUERY_URL
    import requests
    
    # Query 1: ALL companies across ALL graphs (no default-graph-uri)
    q1 = """
    SELECT ?g ?s ?name ?type WHERE {
      GRAPH ?g {
        ?s rdf:type/rdfs:subClassOf* :Company .
        OPTIONAL { ?s :companyName ?name }
        OPTIONAL { ?s rdf:type ?type }
      }
    }
    ORDER BY ?name
    """
    
    # Query 2: Companies in DEFAULT graph only
    q2 = """
    SELECT ?s ?name ?type WHERE {
      ?s rdf:type/rdfs:subClassOf* :Company .
      OPTIONAL { ?s :companyName ?name }
      OPTIONAL { ?s rdf:type ?type }
    }
    ORDER BY ?name
    """
    
    # Query 3: Companies in NAMED graph only
    q3 = """
    SELECT ?s ?name ?type WHERE {
      GRAPH <http://www.transport-ontology.org/travel> {
        ?s rdf:type/rdfs:subClassOf* :Company .
        OPTIONAL { ?s :companyName ?name }
        OPTIONAL { ?s rdf:type ?type }
      }
    }
    ORDER BY ?name
    """
    
    headers = {'Accept': 'application/sparql-results+json'}
    
    try:
        # Execute queries
        resp1 = requests.get(FUSEKI_QUERY_URL, params={'query': SPARQL_PREFIXES + q1}, headers=headers, timeout=15)
        all_graphs = resp1.json() if resp1.status_code == 200 else {"results": {"bindings": []}}
        
        resp2 = requests.get(FUSEKI_QUERY_URL, params={'query': SPARQL_PREFIXES + q2}, headers=headers, timeout=15)
        default_graph = resp2.json() if resp2.status_code == 200 else {"results": {"bindings": []}}
        
        resp3 = requests.get(FUSEKI_QUERY_URL, params={'query': SPARQL_PREFIXES + q3}, headers=headers, timeout=15)
        named_graph = resp3.json() if resp3.status_code == 200 else {"results": {"bindings": []}}
        
        return render(request, 'core/company/debug.html', {
            'all_graphs': all_graphs.get('results', {}).get('bindings', []),
            'default_graph': default_graph.get('results', {}).get('bindings', []),
            'named_graph': named_graph.get('results', {}).get('bindings', []),
        })
    except Exception as e:
        return render(request, 'core/company/debug.html', {
            'error': str(e),
            'all_graphs': [],
            'default_graph': [],
            'named_graph': [],
        })