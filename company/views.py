from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import (
    CompanyForm,
    BusCompanyForm,
    MetroCompanyForm,
    TaxiCompanyForm,
    BikeSharingCompanyForm,
)
from .utils.ontology_manager import create_company, get_company, update_company, delete_company, list_companies


def company_list(request):
    companies = list_companies()
    return render(request, "core/company/company_list.html", {"companies": companies})


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
    Form = type_map.get(company.get("type"), CompanyForm)

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

