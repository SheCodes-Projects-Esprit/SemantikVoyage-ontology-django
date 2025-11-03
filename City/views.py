# views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CapitalCityForm, MetropolitanCityForm, TouristicCityForm, IndustrialCityForm
from .utils.ontology_manager import create_city, get_city, update_city, delete_city, list_cities

def city_list(request):
    cities = list_cities()
    return render(request, "core/city/city_list.html", {"cities": cities})

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