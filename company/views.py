# company/views.py - COMPLETE REPLACEMENT
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import BusCompanyForm, MetroCompanyForm, TaxiCompanyForm, BikeSharingCompanyForm
from .utils.ontology_manager import (
    create_company, get_company, update_company, delete_company, list_companies,
    query_all_graphs, cleanup_company_duplicates, update_company_property, escape_sparql_string
)
from .utils.nl_to_sparql_company import company_nl_to_sparql, company_nl_to_sparql_update
import re


def company_list(request):
    companies = list_companies()
    return render(request, "core/company/company_list.html", {"companies": companies})


def company_ai_query(request):
    """AI Query Handler - matches City's functionality exactly"""
    if request.method != 'POST':
        return redirect('company:list')

    user_text = (request.POST.get('q') or '').strip()
    if not user_text:
        messages.error(request, 'Please enter a command.')
        return redirect('company:list')

    lower = user_text.lower()
    is_update = any(k in lower for k in ['add', 'create', 'insert', 'delete', 'remove', 'update', 'modify', 'set'])

    try:
        # ═══════════════════════════════════════════════════════════
        # UPDATE MODE (CREATE/UPDATE/DELETE)
        # ═══════════════════════════════════════════════════════════
        if is_update:
            generated_sparql = ""
            
            # ────────────────────────────────────────────────────────
            # 1. ADD/CREATE HANDLER
            # ────────────────────────────────────────────────────────
            # Pattern: "Add bus company SOTRA" or "Create metro company RATP"
            m = re.search(
                r"(?:add|create)\s+(bus|metro|taxi|bike\s*sharing|bikesharing)?\s*company\s+([\w\-\s]+)",
                user_text,
                flags=re.IGNORECASE
            )
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
                
                # Generate SPARQL for display
                uri = f":company_{name_val.replace(' ', '_')}"
                generated_sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

INSERT DATA {{
  GRAPH <http://www.transport-ontology.org/travel> {{
    {uri} a :{subclass} ;
          :companyName "{escape_sparql_string(name_val)}" .
  }}
}}"""
                
                try:
                    create_company({'name': name_val, 'type': subclass})
                    cleanup_company_duplicates(name_val)
                    messages.success(request, f"✅ Company '{name_val}' created successfully!")
                except Exception as e:
                    messages.error(request, f"❌ Creation failed: {e}")
                    return redirect('company:list')
                
                import time
                time.sleep(0.3)
                companies = list_companies()
                return render(request, 'core/company/company_list.html', {
                    'companies': companies,
                    'ai_query': user_text,
                    'ai_sparql': generated_sparql,
                })
            
            # ────────────────────────────────────────────────────────
            # 2. UPDATE HANDLER
            # ────────────────────────────────────────────────────────
            # Enhanced patterns:
            # - "Update SOTRA set employees=5000"
            # - "Update SOTRA set employees=5000, headquarters=Tunis"
            # - "Update company where name = SOTRA set employees=5000"
            
            update_match1 = re.search(
                r"update\s+([\w\-\s]+?)\s+set\s+(.+)",
                user_text,
                flags=re.IGNORECASE
            )
            update_match2 = re.search(
                r"update\s+company\s+where\s+name\s*=\s*['\"]?([\w\-\s]+)['\"]?\s+set\s+(.+)",
                user_text,
                flags=re.IGNORECASE
            )
            
            company_name = None
            set_clause = None
            
            if update_match2:
                company_name = update_match2.group(1).strip()
                set_clause = update_match2.group(2).strip()
            elif update_match1:
                candidate = update_match1.group(1).strip()
                # Exclude keywords
                if candidate.lower() not in ['company', 'where', 'name', 'set']:
                    company_name = candidate
                    set_clause = update_match1.group(2).strip()
            
            if company_name and set_clause:
                # Check if company exists
                company = get_company(company_name)
                if not company:
                    messages.error(request, f"❌ Company '{company_name}' not found in RDF store.")
                    return redirect('company:list')
                
                # VALID PROPERTIES MAP
                property_map = {
                    'employees': 'employees',
                    'numberofemployees': 'employees',
                    'year': 'year',
                    'foundedyear': 'year',
                    'headquarters': 'headquarters',
                    'hq': 'headquarters',
                    'headquarterslocation': 'headquarters',
                    'buslines': 'buslines',
                    'numberofbuslines': 'buslines',
                    'lines': 'lines',
                    'numberoflines': 'lines',
                    'vehicles': 'vehicles',
                    'numberofvehicles': 'vehicles',
                    'stations': 'stations',
                    'numberofstations': 'stations',
                    'bikes': 'bikes',
                    'bikecount': 'bikes',
                    'fare': 'fare',
                    'averagefarepe rkm': 'fare',
                    'ticket': 'ticket',
                    'ticketprice': 'ticket',
                    'tracklength': 'trackLength',
                    'track': 'track',
                    'totaltracklength': 'track',
                    'automation': 'automation',
                    'automationlevel': 'automation',
                    'passengers': 'passengers',
                    'dailypassengers': 'passengers',
                    'app': 'app',
                    'bookingapp': 'app',
                    'hasbookingapp': 'app',
                    'eco': 'eco',
                    'ecofriendlyfleet': 'eco',
                    'electric': 'electric',
                    'electricbikes': 'electric',
                    'price': 'price',
                    'subscriptionprice': 'price',
                    'bugage': 'bugage',
                    'age': 'age',
                    'averagebugage': 'age',
                }
                
                # Parse assignments: "prop1=val1, prop2=val2" or "prop1=val1 and prop2=val2"
                assignments = re.split(r',|\band\b', set_clause, flags=re.IGNORECASE)
                
                property_updates = {}
                invalid_props = []
                
                for assignment in assignments:
                    match = re.match(r"(\w+)\s*[=:]\s*(.+)", assignment.strip())
                    if not match:
                        continue
                    
                    prop_name = match.group(1).strip().lower().replace('_', '').replace(' ', '')
                    prop_value = match.group(2).strip().strip('"\'')
                    
                    # Validate property
                    if prop_name not in property_map:
                        invalid_props.append(prop_name)
                        continue
                    
                    mapped_prop = property_map[prop_name]
                    property_updates[mapped_prop] = prop_value
                
                # Show error if invalid properties found
                if invalid_props:
                    valid_list = ', '.join(sorted(set(['employees', 'year', 'headquarters', 'buslines', 'lines', 'vehicles', 'stations', 'bikes', 'fare', 'ticket', 'track', 'automation', 'passengers', 'app', 'eco', 'electric', 'price', 'age'])))
                    messages.error(request, f"❌ Invalid property: '{', '.join(invalid_props)}'. Valid properties: {valid_list}")
                    return redirect('company:list')
                
                if not property_updates:
                    messages.error(request, "❌ No valid properties found to update.")
                    return redirect('company:list')
                
                # Generate SPARQL for display
                rdf_prop_map = {
                    'employees': ':numberOfEmployees',
                    'year': ':foundedYear',
                    'headquarters': ':headquartersLocation',
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
                del_lines = []
                ins_lines = []
                
                for prop, val in property_updates.items():
                    rdf_prop = rdf_prop_map.get(prop.lower(), f":{prop}")
                    
                    # Format value based on type
                    if str(val).lower() in ['true', 'false']:
                        fmt_val = str(val).lower()
                    elif str(val).replace('.', '').replace('-', '').isdigit():
                        fmt_val = str(val)
                    else:
                        fmt_val = f'"{escape_sparql_string(str(val))}"'
                    
                    del_lines.append(f"    {uri} {rdf_prop} ?old_{prop} .")
                    ins_lines.append(f"    {uri} {rdf_prop} {fmt_val} .")
                
                generated_sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

WITH <http://www.transport-ontology.org/travel>
DELETE {{
{chr(10).join(del_lines)}
}}
INSERT {{
{chr(10).join(ins_lines)}
}}
WHERE {{
  {uri} a ?type .
  {chr(10).join([f"  OPTIONAL {{ {line} }}" for line in del_lines])}
}}"""
                
                try:
                    update_company_property(company_name, property_updates)
                    messages.success(request, f"✅ Company '{company_name}' updated successfully!")
                except Exception as e:
                    messages.error(request, f"❌ Update failed: {e}")
                    return redirect('company:list')
                
                import time
                time.sleep(0.3)
                companies = list_companies()
                return render(request, 'core/company/company_list.html', {
                    'companies': companies,
                    'ai_query': user_text,
                    'ai_sparql': generated_sparql,
                })
            
            # ────────────────────────────────────────────────────────
            # 3. DELETE HANDLER
            # ────────────────────────────────────────────────────────
            # Enhanced patterns:
            # - "Delete SOTRA"
            # - "Delete company SOTRA"
            # - "Delete company where name = SOTRA"
            # - "Remove company SOTRA"
            
            delete_match1 = re.search(
                r"(?:delete|remove)\s+company\s+where\s+name\s*=\s*['\"]?([\w\-\s]+)['\"]?",
                user_text,
                flags=re.IGNORECASE
            )
            delete_match2 = re.search(
                r"(?:delete|remove)\s+(?:company\s+)?([a-zA-Z0-9\-\s]+)$",
                user_text,
                flags=re.IGNORECASE
            )
            
            target_name = None
            if delete_match1:
                target_name = delete_match1.group(1).strip()
            elif delete_match2:
                candidate = delete_match2.group(1).strip()
                # Prevent deleting common words accidentally
                if candidate.lower() not in ['company', 'companies', 'all', 'everything', 'where', 'name', 'from', 'the']:
                    target_name = candidate
            
            if target_name:
                # Check if company exists before deleting
                company = get_company(target_name)
                if not company:
                    messages.warning(request, f"⚠️ No company named '{target_name}' found to delete.")
                    return redirect('company:list')
                
                # Generate SPARQL for display
                uri = f":company_{target_name.replace(' ', '_')}"
                generated_sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>

DELETE WHERE {{
  {uri} ?p ?o
}}

WITH <http://www.transport-ontology.org/travel>
DELETE WHERE {{
  {uri} ?p ?o
}}"""
                
                try:
                    if delete_company(target_name):
                        messages.success(request, f"✅ Company '{target_name}' deleted successfully!")
                    else:
                        messages.warning(request, f"⚠️ Delete operation completed, but company may not have existed.")
                except Exception as e:
                    messages.error(request, f"❌ Delete failed: {e}")
                    return redirect('company:list')
                
                import time
                time.sleep(0.3)
                companies = list_companies()
                return render(request, 'core/company/company_list.html', {
                    'companies': companies,
                    'ai_query': user_text,
                    'ai_sparql': generated_sparql,
                })
            
            # Fallback: couldn't parse the update command
            messages.error(request, "❌ Could not parse your command. Please use format: 'Add/Update/Delete company ...'")
            return redirect('company:list')
        
        # ═══════════════════════════════════════════════════════════
        # QUERY MODE (SELECT)
        # ═══════════════════════════════════════════════════════════
        else:
            # Check for specific name search
            name_match = re.search(r"name\s*=\s*['\"]?([\w\-\s]+)['\"]?", user_text, re.IGNORECASE)
            if name_match:
                target = name_match.group(1).strip()
                sparql = f"""
SELECT ?name ?type ?employees ?year ?hq
WHERE {{
  ?c a/rdfs:subClassOf* :Company ; :companyName ?name .
  FILTER(LCASE(?name) = "{target.lower()}")
  OPTIONAL {{ ?c rdf:type ?type }}
  OPTIONAL {{ ?c :numberOfEmployees ?employees }}
  OPTIONAL {{ ?c :foundedYear ?year }}
  OPTIONAL {{ ?c :headquartersLocation ?hq }}
}} LIMIT 10
"""
            else:
                # Use AI-generated SPARQL
                sparql = company_nl_to_sparql(user_text)

            if not sparql:
                messages.error(request, '❌ Could not generate SPARQL query.')
                return redirect('company:list')

            # Execute query across all graphs
            data = query_all_graphs(sparql)
            bindings = data.get('results', {}).get('bindings', [])
            
            if not bindings:
                messages.info(request, "ℹ️ No results found for your query.")
                companies = list_companies()
                return render(request, 'core/company/company_list.html', {
                    'companies': companies,
                    'ai_query': user_text,
                    'ai_sparql': sparql,
                })

            # Extract company names and fetch full details
            selected_names = []
            for b in bindings:
                name = b.get('name', {}).get('value') or b.get('companyName', {}).get('value')
                if name:
                    selected_names.append(name)
            
            companies = []
            for name in selected_names:
                c = get_company(name)
                if c:
                    # Map to list view format
                    c['employees'] = c.get('number_of_employees')
                    c['year'] = c.get('founded_year')
                    c['hq'] = c.get('headquarters_location')
                    c['busLines'] = c.get('number_of_bus_lines')
                    c['metroLines'] = c.get('number_of_lines')
                    c['vehicles'] = c.get('number_of_vehicles')
                    c['stations'] = c.get('number_of_stations')
                    c['bikes'] = c.get('bike_count')
                    c['fare'] = c.get('average_fare_per_km')
                    c['type'] = c.get('type', 'Company').replace('Company', '')
                    companies.append(c)

            return render(request, 'core/company/company_list.html', {
                'companies': companies,
                'ai_query': user_text,
                'ai_sparql': sparql,
            })

    except Exception as e:
        import traceback
        print(f"[ERROR] {e}")
        print(traceback.format_exc())
        messages.error(request, f"❌ Error: {e}")
        return redirect('company:list')


# ═══════════════════════════════════════════════════════════════════
# CRUD VIEWS (Form-based - unchanged)
# ═══════════════════════════════════════════════════════════════════

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
    company_type, Form = type_map.get(
        type_.title() if type_.lower() != 'bikesharing' else 'BikeSharing',
        ("BusCompany", BusCompanyForm)
    )

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
    return render(request, "core/company/company_form.html", {
        "form": form,
        "is_update": False,
        "type": company_type
    })


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

    return render(request, "core/company/company_form.html", {
        "form": form,
        "name": name,
        "is_update": True,
        "type": company.get("type")
    })


def company_delete(request, name):
    if request.method == "POST":
        if delete_company(name):
            messages.success(request, f"Company '{name}' deleted!")
        else:
            messages.error(request, "Delete failed.")
        return redirect("company:list")
    company = get_company(name)
    return render(request, "core/company/company_delete_confirm.html", {
        "company": company,
        "name": name
    })


def company_debug(request):
    """Debug view to see what's in each graph (optional - for troubleshooting)"""
    from .utils.ontology_manager import query_all_graphs, SPARQL_PREFIXES, FUSEKI_QUERY_URL
    from django.http import JsonResponse
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
        
        return JsonResponse({
            'all_graphs_count': len(all_graphs.get('results', {}).get('bindings', [])),
            'default_graph_count': len(default_graph.get('results', {}).get('bindings', [])),
            'named_graph_count': len(named_graph.get('results', {}).get('bindings', [])),
            'all_graphs': all_graphs.get('results', {}).get('bindings', []),
            'default_graph': default_graph.get('results', {}).get('bindings', []),
            'named_graph': named_graph.get('results', {}).get('bindings', []),
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'all_graphs': [],
            'default_graph': [],
            'named_graph': [],
        })