# views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CapitalCityForm, MetropolitanCityForm, TouristicCityForm, IndustrialCityForm
from .utils.ontology_manager import create_city, get_city, update_city, delete_city, list_cities, city_sparql_update, query_all_graphs, cleanup_city_duplicates, delete_city_by_name
from .utils.nl_to_sparql_city import city_nl_to_sparql, city_nl_to_sparql_update
from core.utils.fuseki import sparql_query

def city_list(request):
    cities = list_cities()
    return render(request, "core/city/city_list.html", {"cities": cities})


def city_ai_query(request):
    """Accept a natural-language command, generate SPARQL, execute, and render results on the list page."""
    if request.method != 'POST':
        return redirect('city:list')

    user_text = (request.POST.get('q') or '').strip()
    if not user_text:
        messages.error(request, 'Please enter a command.')
        return redirect('city:list')

    # Heuristic: choose UPDATE vs SELECT
    lower = user_text.lower()
    is_update = any(k in lower for k in ['add ', 'create', 'insert', 'delete', 'remove', 'update', 'modify'])

    try:
        # Lightweight deterministic parser for common patterns to avoid LLM stickiness
        import re
        name_match = re.search(r"name\s*=\s*['\"]?([\w\-\s]+)['\"]?", user_text, flags=re.IGNORECASE)
        
        # Generate SPARQL first (for display purposes)
        if not is_update and name_match:
            target = name_match.group(1).strip()
            sparql = (
                "PREFIX : <http://www.transport-ontology.org/travel#>\n"
                "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
                "SELECT ?name ?pop ?area\nWHERE {\n"
                "  ?c a/rdfs:subClassOf* :City ; :cityName ?name .\n"
                f"  FILTER(LCASE(?name) = \"{target.lower()}\")\n"
                "  OPTIONAL { ?c :population ?pop }\n"
                "  OPTIONAL { ?c :area ?area }\n"
                "}\nLIMIT 10\n"
            )
        else:
            sparql = city_nl_to_sparql_update(user_text) if is_update else city_nl_to_sparql(user_text)
        
        if not sparql:
            messages.error(request, 'Could not generate SPARQL for your command.')
            return redirect('city:list')

        if is_update:
            # Deterministic ADD handler: "Add <type> city <name>" or "Add city <name>"
            import re
            added = False
            m = re.search(r"add\s+(capital|metropolitan|touristic|industrial)?\s*city\s+([\w\-\s]+)", user_text, flags=re.IGNORECASE)
            if m:
                tword = (m.group(1) or '').strip().lower()
                name_val = m.group(2).strip()
                type_map = {
                    'capital': 'CapitalCity',
                    'metropolitan': 'MetropolitanCity',
                    'touristic': 'TouristicCity',
                    'industrial': 'IndustrialCity',
                }
                subclass = type_map.get(tword, 'City')
                
                # Generate SPARQL for display
                uri = f":city_{name_val.replace(' ', '_')}"
                sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

INSERT DATA {{
  GRAPH <http://www.transport-ontology.org/travel> {{
    {uri} a :{subclass} ;
          :cityName "{name_val}" .
  }}
}}"""
                
                # Use existing create_city util for reliability
                try:
                    create_city({'name': name_val}, subclass.replace('City',''))
                except Exception:
                    # fallback to direct SPARQL if util fails
                    city_sparql_update(sparql)
                # Remove any legacy duplicates created by previous AI patterns
                cleanup_city_duplicates(name_val)
                added = True
                messages.success(request, f"✅ City '{name_val}' created!")
                
                # Return with SPARQL displayed
                cities = list_cities()
                return render(request, 'core/city/city_list.html', {
                    'cities': cities,
                    'ai_query': user_text,
                    'ai_sparql': sparql,
                })
            
            # Deterministic DELETE handler: Enhanced to catch both formats
            if not added:
                # Try full format first: "delete city where name = X"
                mdel = re.search(r"delete\s+city\s+where\s+name\s*=\s*['\"]?([\w\-\s]+)['\"]?", user_text, flags=re.IGNORECASE)
                
                # If not matched, try simple format: "delete X" or "delete city X"
                if not mdel:
                    mdel = re.search(r"delete\s+(?:city\s+)?([\w\-\s]+)$", user_text, flags=re.IGNORECASE)
                
                if mdel:
                    targ = mdel.group(1).strip()
                    
                    # Prevent deleting common words accidentally
                    if targ.lower() in ['city', 'cities', 'all', 'everything', 'where', 'name']:
                        messages.error(request, f"❌ Invalid city name '{targ}'. Please specify a valid city name.")
                        return redirect('city:list')
                    
                    # Generate SPARQL for display
                    uri = f":city_{targ.replace(' ', '_')}"
                    sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>

DELETE WHERE {{
  {uri} ?p ?o
}}

WITH <http://www.transport-ontology.org/travel>
DELETE WHERE {{
  {uri} ?p ?o
}}"""
                    
                    if delete_city_by_name(targ):
                        messages.success(request, f"✅ City '{targ}' deleted successfully!")
                    else:
                        messages.warning(request, f"⚠️ No city named '{targ}' found to delete.")
                    
                    cities = list_cities()
                    return render(request, 'core/city/city_list.html', {
                        'cities': cities,
                        'ai_query': user_text,
                        'ai_sparql': sparql,
                    })
            
            # Deterministic UPDATE handler with validation
            if not added:
                # Enhanced pattern to catch both formats:
                # "Update city where name = X set Y" AND "Update X set Y"
                mupd = re.search(
                    r"update\s+(?:city\s+where\s+name\s*=\s*)?['\"]?([\w\-\s]+)['\"]?\s+set\s+(.+)$",
                    user_text,
                    flags=re.IGNORECASE
                )
                if mupd:
                    old = mupd.group(1).strip()
                    assigns = mupd.group(2).strip()
                    new_data = {}
                    
                    # VALID PROPERTIES FOR CITIES
                    valid_props = {
                        'name', 'city', 'cityname',
                        'population', 'pop',
                        'area', 'area_km2',
                        'type',
                        'ministries', 'numberofministries',
                        'districts', 'numberofdistricts',
                        'visitors', 'annualvisitors',
                        'factories', 'numberoffactories',
                        'pollution', 'pollutionindex',
                        'hotels', 'hotelcount',
                        'commute', 'averagecommutetime',
                        'governmentseat'
                    }
                    
                    invalid_props = []
                    
                    for part in re.split(r",|\band\b", assigns, flags=re.IGNORECASE):
                        if '=' in part:
                            k, v = part.split('=', 1)
                        elif ':' in part:
                            k, v = part.split(':', 1)
                        else:
                            continue
                        
                        k = k.strip().lower()
                        v = v.strip().strip('"\'')
                        
                        # VALIDATE PROPERTY
                        if k not in valid_props:
                            invalid_props.append(k)
                            continue
                        
                        # Map to internal field names
                        if k in ['name', 'city', 'cityname']:
                            new_data['name'] = v
                        elif k in ['population', 'pop']:
                            new_data['population'] = v
                        elif k in ['area', 'area_km2']:
                            new_data['area_km2'] = v
                        elif k in ['type']:
                            vv = v.lower()
                            if vv.startswith('cap'): new_data['type'] = 'Capital'
                            elif vv.startswith('met'): new_data['type'] = 'Metropolitan'
                            elif vv.startswith('tou'): new_data['type'] = 'Touristic'
                            elif vv.startswith('ind'): new_data['type'] = 'Industrial'
                        elif k in ['ministries', 'numberofministries']:
                            new_data['ministries'] = v
                        elif k in ['districts', 'numberofdistricts']:
                            new_data['districts'] = v
                        elif k in ['visitors', 'annualvisitors']:
                            new_data['annual_visitors'] = v
                        elif k in ['factories', 'numberoffactories']:
                            new_data['factories'] = v
                        elif k in ['pollution', 'pollutionindex']:
                            new_data['pollution_index'] = v
                        elif k in ['hotels', 'hotelcount']:
                            new_data['hotels'] = v
                        elif k in ['commute', 'averagecommutetime']:
                            new_data['commute_minutes'] = v
                        elif k in ['governmentseat']:
                            new_data['government_seat'] = v.lower() in ['true', 'yes', '1']
                    
                    # Show error if invalid properties found
                    if invalid_props:
                        valid_list = ', '.join(sorted(set(['name', 'population', 'area', 'type', 'ministries', 'districts', 'visitors', 'factories', 'pollution', 'hotels', 'commute'])))
                        messages.error(request, f"❌ Invalid property: '{', '.join(invalid_props)}'. Valid properties for City: {valid_list}")
                        return redirect('city:list')
                    
                    if not new_data:
                        messages.error(request, "❌ No valid properties found to update.")
                        return redirect('city:list')
                    
                    if 'name' not in new_data:
                        new_data['name'] = old
                    
                    # Check if city exists
                    existing = get_city(old)
                    if not existing:
                        messages.error(request, f"❌ City '{old}' not found in RDF store.")
                        return redirect('city:list')
                    
                    # Preserve type if not specified
                    if 'type' not in new_data:
                        new_data['type'] = existing.get('type', 'Capital')
                    
                    # Generate SPARQL for display
                    uri = f":city_{old.replace(' ', '_')}"
                    del_lines = []
                    ins_lines = []
                    
                    prop_map = {
                        'population': ':population',
                        'area_km2': ':area',
                        'ministries': ':numberOfMinistries',
                        'districts': ':numberOfDistricts',
                        'annual_visitors': ':annualVisitors',
                        'factories': ':numberOfFactories',
                        'pollution_index': ':pollutionIndex',
                        'hotels': ':hotelCount',
                        'commute_minutes': ':averageCommuteTime',
                    }
                    
                    for k, v in new_data.items():
                        if k == 'name' and v == old:
                            continue
                        if k == 'type':
                            continue
                        
                        rdf_prop = prop_map.get(k, f":{k}")
                        
                        # Format value
                        if isinstance(v, bool) or str(v).lower() in ['true', 'false']:
                            fmt_val = str(v).lower()
                        elif str(v).replace('.', '').replace('-', '').isdigit():
                            fmt_val = str(v)
                        else:
                            fmt_val = f'"{v}"'
                        
                        del_lines.append(f"    {uri} {rdf_prop} ?old_{k} .")
                        ins_lines.append(f"    {uri} {rdf_prop} {fmt_val} .")
                    
                    sparql = f"""PREFIX : <http://www.transport-ontology.org/travel#>

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
                    
                    update_city(old, new_data)
                    cleanup_city_duplicates(new_data['name'])
                    messages.success(request, f"✅ City '{old}' updated successfully!")
                    
                    cities = list_cities()
                    return render(request, 'core/city/city_list.html', {
                        'cities': cities,
                        'ai_query': user_text,
                        'ai_sparql': sparql,
                    })
            
            # Fallback to LLM-generated SPARQL for other update patterns
            if not added:
                city_sparql_update(sparql)
                messages.success(request, '✅ Update executed successfully.')
                
                cities = list_cities()
                return render(request, 'core/city/city_list.html', {
                    'cities': cities,
                    'ai_query': user_text,
                    'ai_sparql': sparql,
                })
        else:
            # IMPORTANT: query across ALL graphs so we see ontology + AI + form-created cities
            data = query_all_graphs(sparql)
            bindings = data.get('results', {}).get('bindings', [])
            # Transform bindings into a simple rows list -> {var: value}
            vars_ = list(bindings[0].keys()) if bindings else []
            processed = []
            for b in bindings:
                row = {}
                for v in vars_:
                    val_obj = b.get(v)
                    row[v] = val_obj.get('value', '') if isinstance(val_obj, dict) else ''
                processed.append(row)

            # If the SELECT returned city names, filter the main table to those
            name_keys = ['name', 'cityName']
            selected_names = []
            for r in processed:
                for k in name_keys:
                    if r.get(k):
                        selected_names.append(r.get(k))
                        break
            if selected_names:
                # Build detailed rows via get_city to keep the same table structure
                cities = []
                name_to_row = {r.get('name') or r.get('cityName'): r for r in processed}
                for nm in selected_names:
                    c = get_city(nm)
                    if c:
                        # Ensure list view expects 'area' key
                        if 'area' not in c and 'area_km2' in c:
                            c['area'] = c.get('area_km2')
                        cities.append(c)
                    else:
                        # Fallback: build minimal city row from SELECT values
                        r = name_to_row.get(nm, {})
                        cities.append({
                            'name': nm,
                            'type': 'Unknown',
                            'population': r.get('pop') or 0,
                            'area': r.get('area') or 0,
                        })
            else:
                cities = list_cities()
            
            return render(request, 'core/city/city_list.html', {
                'cities': cities,
                'ai_query': user_text,
                'ai_sparql': sparql,
                'ai_results': bindings,
                'ai_table_vars': vars_,
                'ai_table_rows': processed,
            })
    except Exception as e:
        messages.error(request, f"❌ AI/SPARQL error: {e}")
        cities = list_cities()
        return render(request, 'core/city/city_list.html', {
            'cities': cities,
            'ai_query': user_text if 'user_text' in locals() else '',
            'ai_sparql': sparql if 'sparql' in locals() else '',
        })
               
def city_detail(request, name):
    city = get_city(name)
    if not city:
        messages.error(request, f"City '{name}' not found.")
        return redirect("city:list")
    return render(request, "core/city/city_detail.html", {"city": city})

def city_create(request):
    type_ = request.GET.get("type", "Capital").title()
    Form = {
        "Capital": CapitalCityForm,
        "Metropolitan": MetropolitanCityForm,
        "Touristic": TouristicCityForm,
        "Industrial": IndustrialCityForm
    }[type_]

    if request.method == "POST":
        form = Form(request.POST)
        if form.is_valid():
            data = {**form.cleaned_data, "type": type_}
            try:
                created_name = create_city(data, type_)
                messages.success(request, f"City '{created_name}' created!")
                return redirect("city:detail", name=created_name)
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = Form()
    return render(request, "core/city/city_form.html", {"form": form, "type": type_, "is_update": False})

def city_update(request, name):
    city = get_city(name)
    if not city:
        messages.error(request, "City not found.")
        return redirect("city:list")

    Form = {
        "Capital": CapitalCityForm,
        "Metropolitan": MetropolitanCityForm,
        "Touristic": TouristicCityForm,
        "Industrial": IndustrialCityForm
    }[city["type"]]

    if request.method == "POST":
        form = Form(request.POST, original_name=name)
        if form.is_valid():
            data = {**form.cleaned_data, "type": city["type"]}
            try:
                update_city(name, data)
                messages.success(request, f"City '{data['name']}' updated!")
                return redirect("city:detail", name=data['name'])
            except Exception as e:
                messages.error(request, str(e))
    else:
        init = {k: city.get(k) for k in Form.Meta.fields if k != "city_id"}
        form = Form(initial=init, original_name=name)

    return render(request, "core/city/city_form.html", {
        "form": form, "type": city["type"], "name": name, "is_update": True
    })

def city_delete(request, name):
    if request.method == "POST":
        if delete_city(name):
            messages.success(request, f"City '{name}' deleted!")
        else:
            messages.error(request, "Delete failed.")
        return redirect("city:list")
    city = get_city(name)
    return render(request, "core/city/city_delete_confirm.html", {"city": city, "name": name})