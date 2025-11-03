# itinerary/views.py - FIXED PURE RDF VERSION
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from .forms import BusinessTripForm, LeisureTripForm, EducationalTripForm
from .utils.ontology_manager import (
    create_itinerary, get_itinerary, update_itinerary,
    delete_itinerary, list_itineraries, normalize_itinerary_id,
)
from .utils.ai_generator import generate_itinerary_suggestions
from core.utils.fuseki import sparql_query
from .utils.ai_nl_interface import ai_generate_and_execute


# ----------------------------------------------------------------------
# LIST - Pure RDF
# ----------------------------------------------------------------------
def itinerary_list(request):
    """List all itineraries from RDF store."""
    filters = request.GET.dict()

    # Fetch itineraries from RDF only
    itineraries = list_itineraries(filters)

    # Sort by ID
    itineraries.sort(key=lambda x: x["id"])

    return render(request, "core/itinerary/itinerary_list.html", {
        "itineraries": itineraries,
        "filters": filters,
        "has_unsynced": False,
    })


# ----------------------------------------------------------------------
# DETAIL - Pure RDF
# ----------------------------------------------------------------------
def itinerary_detail(request, id: str):
    """Display single itinerary details from RDF store."""
    subject_uri = request.GET.get("s")
    itinerary = get_itinerary(id, subject_uri=subject_uri)

    if not itinerary:
        messages.error(request, f"Itinerary {id} not found in RDF store.")
        return redirect("itinerary:list")

    # Query related transports and schedules
    related = []
    try:
        sparql = f"""
        PREFIX : <http://www.transport-ontology.org/travel#>
        SELECT ?trans ?sched WHERE {{
          ?it :itineraryID "{id}" ;
              :uses ?trans .
          OPTIONAL {{ ?it :hasSchedule ?sched }}
        }}
        LIMIT 10
        """
        result = sparql_query(sparql)
        
        for b in result.get("results", {}).get("bindings", []):
            related.append({
                "trans": b.get("trans", {}).get("value", "N/A").split('#')[-1],
                "sched": b.get("sched", {}).get("value", "N/A").split('#')[-1]
            })
    except Exception as e:
        print(f"⚠️ Related query error: {e}")

    return render(request, "core/itinerary/itinerary_detail.html", {
        "itinerary": itinerary,
        "related": related,
        "id": id,
        "subject_uri": subject_uri,
    })


# ----------------------------------------------------------------------
# CREATE - Pure RDF
# ----------------------------------------------------------------------
def itinerary_create(request):
    """Create a new itinerary in RDF store only."""
    form_type = request.GET.get("type", "Business").title()
    
    if form_type not in {"Business", "Leisure", "Educational"}:
        messages.error(request, "Invalid itinerary type.")
        return redirect("itinerary:list")

    FormCls = {
        "Business": BusinessTripForm,
        "Leisure": LeisureTripForm,
        "Educational": EducationalTripForm,
    }[form_type]

    if request.method == "POST":
        form = FormCls(request.POST)
        if form.is_valid():
            # Extract and convert form data to RDF format
            cleaned = form.cleaned_data
            
            # Build RDF data dict with correct property names
            data = {
                'itinerary_id': cleaned.get('itinerary_id'),
                'overall_status': cleaned.get('overall_status', 'Planned'),
                'total_cost_estimate': float(cleaned.get('total_cost_estimate') or 0),
                'total_duration_days': int(cleaned.get('total_duration_days') or 1),
            }
            
            # Add type-specific fields
            if form_type == 'Business':
                data.update({
                    'client_project_name': cleaned.get('client_project_name', ''),
                    'expense_limit': float(cleaned.get('expense_limit') or 0),
                    'purpose_code': cleaned.get('purpose_code', ''),
                    'approval_required': bool(cleaned.get('approval_required', False)),
                })
            elif form_type == 'Leisure':
                data.update({
                    'activity_type': cleaned.get('activity_type', ''),
                    'accommodation': cleaned.get('accommodation', ''),
                    'budget_per_day': float(cleaned.get('budget_per_day') or 0),
                    'group_size': int(cleaned.get('group_size') or 1),
                })
            elif form_type == 'Educational':
                data.update({
                    'institution': cleaned.get('institution', ''),
                    'course_reference': cleaned.get('course_reference', ''),
                    'credit_hours': int(cleaned.get('credit_hours') or 0),
                    'required_documentation': cleaned.get('required_documentation', ''),
                })
            
            try:
                # Create in RDF
                created_id = create_itinerary(data, form_type)
                messages.success(request, f"✅ Itinerary {created_id} created successfully in RDF store!")
                return redirect("itinerary:detail", id=created_id)
            
            except Exception as e:
                messages.error(request, f"❌ Failed to create itinerary: {str(e)}")
                print(f"Create error: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = FormCls()

    return render(request, "core/itinerary/itinerary_form.html", {
        "form": form,
        "type": form_type,
        "is_update": False,
    })


# ----------------------------------------------------------------------
# UPDATE - Pure RDF
# ----------------------------------------------------------------------
def itinerary_update(request, id: str):
    """Update an existing itinerary in RDF store only."""
    # Retrieve from RDF
    subject_uri = request.GET.get("s")
    itinerary = get_itinerary(id, subject_uri=subject_uri)
    
    if not itinerary:
        messages.error(request, f"Itinerary {id} not found in RDF store.")
        return redirect("itinerary:list")

    form_type = itinerary.get("type", "Business")
    FormCls = {
        "Business": BusinessTripForm,
        "Leisure": LeisureTripForm,
        "Educational": EducationalTripForm,
    }[form_type]

    # Map RDF property names to Django form field names
    mapping = {
        "overallStatus": "overall_status",
        "totalCostEstimate": "total_cost_estimate",
        "totalDurationDays": "total_duration_days",
        "clientProjectName": "client_project_name",
        "expenseLimit": "expense_limit",
        "purposeCode": "purpose_code",
        "approvalRequired": "approval_required",
        "activityType": "activity_type",
        "accommodation": "accommodation",
        "budgetPerDay": "budget_per_day",
        "groupSize": "group_size",
        "institution": "institution",
        "courseReference": "course_reference",
        "creditHours": "credit_hours",
        "requiredDocumentation": "required_documentation",
    }

    # Convert RDF data to form format
    form_data = {}
    for rdf_key, form_key in mapping.items():
        if rdf_key in itinerary:
            value = itinerary[rdf_key]
            # Convert boolean strings
            if value in ['true', 'false']:
                value = value == 'true'
            # Convert numeric strings
            elif form_key in ['total_cost_estimate', 'expense_limit', 'budget_per_day']:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = 0.0
            elif form_key in ['total_duration_days', 'group_size', 'credit_hours']:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    value = 0
            form_data[form_key] = value
    
    # Extract base ID for form (remove prefix)
    if id.startswith(('I-B-', 'I-L-', 'I-E-')):
        base_id = id.split('-')[-1].lstrip('0') or '0'
    else:
        base_id = id
    form_data['itinerary_id'] = base_id

    if request.method == "POST":
        # Pass original_id to form for validation
        form = FormCls(request.POST, original_id=id)
        if form.is_valid():
            # Extract and convert form data
            cleaned = form.cleaned_data
            
            # Build RDF data dict
            data = {
                'overall_status': cleaned.get('overall_status', 'Planned'),
                'total_cost_estimate': float(cleaned.get('total_cost_estimate') or 0),
                'total_duration_days': int(cleaned.get('total_duration_days') or 1),
                'type': form_type,
            }
            
            # Add type-specific fields
            if form_type == 'Business':
                data.update({
                    'client_project_name': cleaned.get('client_project_name', ''),
                    'expense_limit': float(cleaned.get('expense_limit') or 0),
                    'purpose_code': cleaned.get('purpose_code', ''),
                    'approval_required': bool(cleaned.get('approval_required', False)),
                })
            elif form_type == 'Leisure':
                data.update({
                    'activity_type': cleaned.get('activity_type', ''),
                    'accommodation': cleaned.get('accommodation', ''),
                    'budget_per_day': float(cleaned.get('budget_per_day') or 0),
                    'group_size': int(cleaned.get('group_size') or 1),
                })
            elif form_type == 'Educational':
                data.update({
                    'institution': cleaned.get('institution', ''),
                    'course_reference': cleaned.get('course_reference', ''),
                    'credit_hours': int(cleaned.get('credit_hours') or 0),
                    'required_documentation': cleaned.get('required_documentation', ''),
                })
            
            try:
                # Update in RDF
                updated_id = update_itinerary(id, data, subject_uri=subject_uri)
                messages.success(request, f"✅ Itinerary {id} updated successfully!")
                return redirect("itinerary:detail", id=id)
            
            except Exception as e:
                messages.error(request, f"❌ Failed to update itinerary: {str(e)}")
                print(f"Update error: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = FormCls(initial=form_data, original_id=id)

    return render(request, "core/itinerary/itinerary_form.html", {
        "form": form,
        "type": form_type,
        "id": id,
        "is_update": True,
        "subject_uri": subject_uri,
    })


# ----------------------------------------------------------------------
# DELETE - Pure RDF
# ----------------------------------------------------------------------
def itinerary_delete(request, id: str):
    """Delete an itinerary from RDF store only."""
    subject_uri = request.GET.get("s")
    if request.method == "POST":
        try:
            # Delete from RDF only
            deleted = delete_itinerary(id, subject_uri=subject_uri)
            
            if deleted:
                messages.success(request, f"✅ Itinerary {id} deleted successfully!")
            else:
                messages.warning(request, f"⚠️ Itinerary {id} may not have been fully deleted.")
            
        except Exception as e:
            messages.error(request, f"❌ Delete error: {str(e)}")
            print(f"Delete error: {e}")
            import traceback
            traceback.print_exc()
        
        return redirect("itinerary:list")

    # GET request - show confirmation page
    itinerary = get_itinerary(id, subject_uri=subject_uri)
    
    if not itinerary:
        messages.error(request, f"Itinerary {id} not found.")
        return redirect("itinerary:list")

    return render(request, "core/itinerary/itinerary_delete_confirm.html", {
        "id": id,
        "itinerary": itinerary,
        "subject_uri": subject_uri,
    })


# ----------------------------------------------------------------------
# AI SUGGESTION
# ----------------------------------------------------------------------
def itinerary_ai_suggest(request):
    """Generate AI-powered itinerary suggestions."""
    if request.method == "POST":
        prefs = request.POST.dict()
        try:
            suggestions = generate_itinerary_suggestions(prefs)
            
            if "error" in suggestions:
                return JsonResponse({"error": suggestions["error"]}, status=400)
            
            return JsonResponse({"suggestions": suggestions})
        
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return render(request, "core/itinerary/itinerary_ai_suggest.html")


# ----------------------------------------------------------------------
# AI NL QUERY CONSOLE (JSON API)
# ----------------------------------------------------------------------
def itinerary_ai_query(request):
    """NL -> SPARQL endpoint for SELECT/UPDATE, returns JSON."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    payload = request.POST.dict()
    nl_text = payload.get("query") or payload.get("q") or ""
    result = ai_generate_and_execute(nl_text)

    status = 200 if "error" not in result else 400
    return JsonResponse(result, status=status)