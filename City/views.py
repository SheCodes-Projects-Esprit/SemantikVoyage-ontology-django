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
                # Use existing create_city util for reliability
                try:
                    create_city({'name': name_val}, subclass.replace('City',''))
                except Exception:
                    # fallback to direct SPARQL if util fails
                    uri = f":city_{name_val.replace(' ', '_')}"
                    sparql = (
                        f"PREFIX : <http://www.transport-ontology.org/travel#>\n"
                        f"INSERT DATA {{ GRAPH <http://www.transport-ontology.org/travel> {{\n"
                        f"  {uri} a :{subclass} ; :cityName \"{name_val}\" .\n"
                        f"}} }}\n"
                    )
                    city_sparql_update(sparql)
                # Remove any legacy duplicates created by previous AI patterns
                cleanup_city_duplicates(name_val)
                added = True
            # Deterministic DELETE handler: "Delete city where name = X"
            if not added:
                mdel = re.search(r"delete\s+city\s+where\s+name\s*=\s*['\"]?([\w\-\s]+)['\"]?", user_text, flags=re.IGNORECASE)
                if mdel:
                    targ = mdel.group(1).strip()
                    if delete_city_by_name(targ):
                        messages.success(request, f"City '{targ}' deleted!")
                    else:
                        messages.warning(request, f"No city named '{targ}' found to delete.")
                    return redirect('city:list')
            # Deterministic UPDATE handler: "Update city where name = X set population = 123 area = 45 type = Touristic name = Y"
            if not added:
                mupd = re.search(r"update\s+city\s+where\s+name\s*=\s*['\"]?([\w\-\s]+)['\"]?\s*(set|to)\s*(.+)$", user_text, flags=re.IGNORECASE)
                if mupd:
                    old = mupd.group(1).strip()
                    assigns = mupd.group(3).strip()
                    new_data = {}
                    for part in re.split(r",|\band\b", assigns, flags=re.IGNORECASE):
                        if '=' in part:
                            k,v = part.split('=',1)
                        elif ':' in part:
                            k,v = part.split(':',1)
                        else:
                            continue
                        k = k.strip().lower()
                        v = v.strip().strip('"\'')
                        if k in ['name','city','cityname']:
                            new_data['name'] = v
                        elif k in ['population','pop']:
                            new_data['population'] = v
                        elif k in ['area','area_km2']:
                            new_data['area_km2'] = v
                        elif k in ['type']:
                            vv = v.lower()
                            if vv.startswith('cap'): new_data['type']='Capital'
                            elif vv.startswith('met'): new_data['type']='Metropolitan'
                            elif vv.startswith('tou'): new_data['type']='Touristic'
                            elif vv.startswith('ind'): new_data['type']='Industrial'
                    if 'name' not in new_data:
                        new_data['name'] = old
                    update_city(old, new_data)
                    cleanup_city_duplicates(new_data['name'])
                    messages.success(request, f"City '{old}' updated!")
                    return redirect('city:list')
            if not added:
                # Run through City-local updater that always targets the ontology graph
                city_sparql_update(sparql)
            messages.success(request, 'Update executed successfully.')
            return redirect('city:list')
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
        messages.error(request, f"AI/SPARQL error: {e}")
        return redirect('city:list')

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