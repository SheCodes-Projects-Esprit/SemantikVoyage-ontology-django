from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
import requests
import json

from .models import (
    Station, Transport, BusStop, MetroStation, TrainStation, TramStation, 
    Bus, Metro, Train, Tram, City, Company, BusCompany, MetroCompany, 
    Schedule, DailySchedule, Person, Conducteur, Contrôleur, EmployéAgence, Passager
)
from .forms import StationForm, TransportForm, PersonForm

# Import des services ontologie
try:
    from .services.ontology_service import OntologySyncService
    from core.utils.nl_to_sparql import nl_to_sparql, nl_to_sparql_update
    from core.utils.fuseki import sparql_query, sparql_update
    ONTOLOGY_AVAILABLE = True
except ImportError as e:
    print(f"Ontology services not available: {e}")
    ONTOLOGY_AVAILABLE = False

# ==================== STATIONS ====================

def list_stations(request):
    stations = []
    for subclass in Station.__subclasses__():
        qs = subclass.objects.select_related('located_in')
        for obj in qs:
            transports = set()
            for transport_cls in Transport.__subclasses__():
                departures = getattr(obj, f'{transport_cls.__name__.lower()}_departures', None)
                arrivals = getattr(obj, f'{transport_cls.__name__.lower()}_arrivals', None)
                if departures:
                    transports.update(departures.all())
                if arrivals:
                    transports.update(arrivals.all())
            obj.get_all_transports = transports
            stations.append(obj)

    # Query ontology for additional station data
    ontology_stations = []
    if ONTOLOGY_AVAILABLE:
        try:
            # REQUÊTE SPARQL CORRECTE - même format que votre code fonctionnel
            sparql = """
            PREFIX : <http://www.transport-ontology.org/travel#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?station ?name ?location ?accessibility
            WHERE {
                ?station a/rdfs:subClassOf* :Station ;
                        :Station_hasName ?name .
                OPTIONAL { ?station :Station_hasLocation ?location }
                OPTIONAL { ?station :Station_hasAccessibility ?accessibility }
            }
            LIMIT 20
            """
            result = sparql_query(sparql)
            ontology_stations = result.get('results', {}).get('bindings', [])
            
        except Exception as e:
            print(f"[ERROR] Erreur requete ontologie: {e}")
            messages.warning(request, f"Impossible de charger les données de l'ontologie: {e}")

    return render(request, 'list_stations.html', {
        'stations': stations,
        'ontology_stations': ontology_stations,
        'ontology_available': ONTOLOGY_AVAILABLE
    })

def create_station(request):
    if request.method == 'POST':
        form = StationForm(request.POST)
        if form.is_valid():
            try:
                station = form.save()
                
                # Sync to ontology if available
                if ONTOLOGY_AVAILABLE:
                    try:
                        sync_service = OntologySyncService()
                        sync_service.sync_station_to_ontology(station)
                        messages.success(request, "Station créée et synchronisée avec l'ontologie !")
                    except Exception as e:
                        messages.warning(request, f"Station créée mais erreur de synchronisation: {e}")
                else:
                    messages.success(request, "Station créée avec succès !")
                
                return redirect('list_stations')
            except Exception as e:
                messages.error(request, f"Erreur: {e}")
    else:
        form = StationForm()
    return render(request, 'station_form.html', {'form': form, 'title': 'Créer une Station'})

def update_station(request, pk):
    station = get_object_or_404(Station, pk=pk)
    if request.method == 'POST':
        form = StationForm(request.POST, instance=station)
        if form.is_valid():
            station = form.save()
            
            # Sync to ontology if available
            if ONTOLOGY_AVAILABLE:
                try:
                    sync_service = OntologySyncService()
                    sync_service.sync_station_to_ontology(station)
                    messages.success(request, "Station modifiée et synchronisée !")
                except Exception as e:
                    messages.warning(request, f"Station modifiée mais erreur de synchronisation: {e}")
            else:
                messages.success(request, "Station modifiée !")
            
            return redirect('list_stations')
    else:
        form = StationForm(instance=station)
    return render(request, 'station_form.html', {
        'form': form,
        'title': 'Modifier la Station'
    })

def delete_station(request, pk):
    station = get_object_or_404(Station, pk=pk)
    if request.method == 'POST':
        # Delete from ontology first if available
        if ONTOLOGY_AVAILABLE:
            try:
                sync_service = OntologySyncService()
                sync_service.delete_station_from_ontology(station)
            except Exception as e:
                messages.warning(request, f"Erreur lors de la suppression de l'ontologie: {e}")
        
        # Then delete from database
        station.delete()
        messages.success(request, "Station supprimée.")
        return redirect('list_stations')
    
    return render(request, 'confirm_delete.html', {
        'object': station,
        'type': 'station'
    })

# ==================== TRANSPORTS ====================

def list_transports(request):
    transports = []
    for subclass in Transport.__subclasses__():
        transports.extend(subclass.objects.all())
    
    # Query ontology for additional transport data
    ontology_transports = []
    if ONTOLOGY_AVAILABLE:
        try:
            sparql = """
                    PREFIX :     <http://www.transport-ontology.org/travel#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                    SELECT ?transport ?line ?capacity ?speed
                    WHERE {
                        ?transport a/rdfs:subClassOf* :Transport ;
                                :Transport_hasLineNumber ?line .
                        OPTIONAL { ?transport :Transport_hasCapacity ?capacity }
                        OPTIONAL { ?transport :Transport_hasSpeed ?speed }
                    }
                    LIMIT 50
                    """
            result = sparql_query(sparql)
            ontology_transports = result.get('results', {}).get('bindings', [])
        except Exception as e:
            messages.warning(request, f"Could not fetch ontology data: {e}")

    return render(request, 'transports_list.html', {
        'transports': transports,
        'ontology_transports': ontology_transports,
        'ontology_available': ONTOLOGY_AVAILABLE
    })

def create_transport(request):
    if request.method == 'POST':
        form = TransportForm(request.POST)
        if form.is_valid():
            try:
                transport = form.save()
                
                # Sync to ontology if available
                if ONTOLOGY_AVAILABLE:
                    try:
                        sync_service = OntologySyncService()
                        sync_service.sync_transport_to_ontology(transport)
                        messages.success(request, "Transport créé et synchronisé avec l'ontologie !")
                    except Exception as e:
                        messages.warning(request, f"Transport créé mais erreur de synchronisation: {e}")
                else:
                    messages.success(request, "Transport créé avec succès !")
                
                return redirect('list_transports')
            except ValidationError as e:
                # Gérer les erreurs de validation
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            except Exception as e:
                messages.error(request, f"Erreur: {e}")
    else:
        form = TransportForm()
    return render(request, 'transport_form.html', {'form': form, 'title': 'Créer un Transport'})

def update_transport(request, pk, model_name):
    model_map = {'bus': Bus, 'metro': Metro, 'train': Train, 'tram': Tram}
    if model_name.lower() not in model_map:
        messages.error(request, "Type de transport invalide.")
        return redirect('list_transports')

    model = model_map[model_name.lower()]
    transport = get_object_or_404(model, pk=pk)

    if request.method == 'POST':
        form = TransportForm(request.POST, instance=transport)
        if form.is_valid():
            new_line = form.cleaned_data['transport_line_number']
            if Transport.objects.exclude(pk=transport.pk).filter(transport_line_number=new_line).exists():
                form.add_error('transport_line_number', 'Cette ligne existe déjà.')
            else:
                try:
                    transport = form.save()
                    
                    # Sync to ontology if available
                    if ONTOLOGY_AVAILABLE:
                        try:
                            sync_service = OntologySyncService()
                            sync_service.sync_transport_to_ontology(transport)
                            messages.success(request, "Transport modifié et synchronisé !")
                        except Exception as e:
                            messages.warning(request, f"Transport modifié mais erreur de synchronisation: {e}")
                    else:
                        messages.success(request, "Transport modifié avec succès !")
                    
                    return redirect('list_transports')
                except ValidationError as e:
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
    else:
        form = TransportForm(instance=transport)

    return render(request, 'transport_form.html', {'form': form, 'title': 'Modifier le Transport'})

def delete_transport(request, pk, model_name):
    model_map = {'bus': Bus, 'metro': Metro, 'train': Train, 'tram': Tram}
    if model_name.lower() not in model_map:
        messages.error(request, "Type de transport invalide.")
        return redirect('list_transports')

    model = model_map[model_name.lower()]
    transport = get_object_or_404(model, pk=pk)

    if request.method == 'POST':
        # Delete from ontology first if available
        if ONTOLOGY_AVAILABLE:
            try:
                sync_service = OntologySyncService()
                sync_service.delete_transport_from_ontology(transport)
            except Exception as e:
                messages.warning(request, f"Erreur lors de la suppression de l'ontologie: {e}")
        
        # Then delete from database
        transport.delete()
        messages.success(request, "Transport supprimé.")
        return redirect('list_transports')

    return render(request, 'confirm_delete.html', {'object': transport, 'type': 'transport'})

# ==================== ONTOLOGY VIEWS ====================

def ontology_query_view(request):
    """View for natural language queries"""
    results_data = None
    generated_sparql = ""
    table_headers = []
    table_rows = []
    
    if not ONTOLOGY_AVAILABLE:
        messages.error(request, "Les services d'ontologie ne sont pas disponibles.")
        return redirect('list_stations')
    
    if request.method == 'POST':
        question = request.POST.get('question', '')
        if question:
            try:
                # Convert natural language to SPARQL
                generated_sparql = nl_to_sparql(question)
                if generated_sparql:
                    # Execute query
                    results_data = sparql_query(generated_sparql)
                    
                    # Preprocess results for template - SANS template tags
                    if results_data and 'results' in results_data and 'bindings' in results_data['results']:
                        table_headers = results_data.get('head', {}).get('vars', [])
                        
                        for binding in results_data['results']['bindings']:
                            row = []
                            for var in table_headers:
                                if var in binding:
                                    row.append(binding[var].get('value', 'N/A'))
                                else:
                                    row.append('N/A')
                            table_rows.append(row)
                    
                else:
                    messages.error(request, "Impossible de générer la requête SPARQL")
            except Exception as e:
                messages.error(request, f"Erreur lors de la requête: {e}")
    
    return render(request, 'ontology_query.html', {
        'sparql_query': generated_sparql,
        'table_headers': table_headers,
        'table_rows': table_rows,
        'results_count': len(table_rows)
    })

def ontology_update_view(request):
    """View for natural language UPDATE operations"""
    update_result = None
    generated_sparql = ""
    
    if not ONTOLOGY_AVAILABLE:
        messages.error(request, "Les services d'ontologie ne sont pas disponibles.")
        return redirect('list_stations')
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        question = request.POST.get('question', '').strip()
        
        if question:
            try:
                if action == 'update':
                    # Use the new UPDATE function
                    generated_sparql = nl_to_sparql_update(question)
                else:
                    # Use the existing SELECT function
                    generated_sparql = nl_to_sparql(question)
                
                if generated_sparql:
                    print(f"[DEBUG] Requete generee: {generated_sparql}")
                    
                    if action == 'update':
                        try:
                            # Execute UPDATE query
                            print("[DEBUG] Execution de la requete UPDATE...")
                            result = sparql_update(generated_sparql)
                            print(f"[OK] UPDATE reussi - Status: {result.status_code}")
                            
                            update_result = {
                                'status': 'success',
                                'message': 'Opération réalisée avec succès !'
                            }
                            
                        except Exception as e:
                            print(f"[ERROR] Erreur UPDATE: {e}")
                            update_result = {
                                'status': 'error',
                                'message': f"Erreur lors de l'exécution: {e}"
                            }
                    else:
                        # Execute SELECT query
                        print("[DEBUG] Execution de la requete SELECT...")
                        results_data = sparql_query(generated_sparql)
                        print(f"[OK] SELECT reussi - {len(results_data.get('results', {}).get('bindings', []))} resultats")
                        
                        # Preprocess results
                        table_headers = []
                        table_rows = []
                        if results_data and 'results' in results_data and 'bindings' in results_data['results']:
                            table_headers = results_data.get('head', {}).get('vars', [])
                            for binding in results_data['results']['bindings']:
                                row = []
                                for var in table_headers:
                                    if var in binding:
                                        row.append(binding[var].get('value', 'N/A'))
                                    else:
                                        row.append('N/A')
                                table_rows.append(row)
                        
                        update_result = {
                            'status': 'query',
                            'headers': table_headers,
                            'rows': table_rows,
                            'count': len(table_rows)
                        }
                    
                else:
                    messages.error(request, "Impossible de générer la requête SPARQL")
            except Exception as e:
                print(f"[ERROR] Erreur generale: {e}")
                update_result = {
                    'status': 'error',
                    'message': f"Erreur: {e}"
                }
    
    return render(request, 'ontology_update.html', {
        'update_result': update_result,
        'sparql_query': generated_sparql
    })

def ontology_operations_view(request):
    """Main view for all ontology operations"""
    return render(request, 'ontology_operations.html')

def sync_all_data_view(request):
    """View to manually sync all data to ontology"""
    if not ONTOLOGY_AVAILABLE:
        messages.error(request, "Les services d'ontologie ne sont pas disponibles.")
        return redirect('list_stations')
    
    if request.method == 'POST':
        try:
            sync_service = OntologySyncService()
            result = sync_service.sync_all_data()
            messages.success(request, f"Synchronisation réussie: {result}")
        except Exception as e:
            messages.error(request, f"Erreur de synchronisation: {e}")
        
        return redirect('list_stations')
    
    return render(request, 'sync_confirmation.html')

def ontology_status_view(request):
    """View to check ontology status"""
    status = {
        'ontology_available': ONTOLOGY_AVAILABLE,
        'fuseki_url': None,
        'dataset': None,
        'graph': None
    }
    
    if ONTOLOGY_AVAILABLE:
        try:
            from django.conf import settings
            status.update({
                'fuseki_url': getattr(settings, 'FUSEKI_URL', 'Non configuré'),
                'dataset': getattr(settings, 'FUSEKI_DATASET', 'Non configuré'),
                'graph': getattr(settings, 'FUSEKI_GRAPH', 'Non configuré')
            })
            
            # Test connection
            test_query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"
            result = sparql_query(test_query)
            status['connection_test'] = 'Réussi' if result else 'Échec'
            
        except Exception as e:
            status['connection_test'] = f'Échec: {e}'
    
    return render(request, 'ontology_status.html', {'status': status})


# ==================== PERSONS ====================

def list_persons(request):
    """List all persons grouped by type"""
    persons = []
    for subclass in Person.__subclasses__():
        qs = subclass.objects.all()
        for obj in qs:
            obj.person_type = subclass.__name__
            persons.append(obj)
    
    # Query ontology for additional person data
    ontology_persons = []
    if ONTOLOGY_AVAILABLE:
        try:
            # Rechercher dans tous les graphes (pas de restriction GRAPH)
            sparql = """
            PREFIX : <http://www.transport-ontology.org/travel#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            
            SELECT DISTINCT ?person ?id ?name ?age ?email ?role ?phoneNumber ?type
            WHERE {
                {
                    ?person a/rdfs:subClassOf* :Person .
                    OPTIONAL { ?person :hasID ?id }
                    OPTIONAL { ?person :hasName ?name }
                }
                UNION
                {
                    ?person :hasID ?id .
                    OPTIONAL { ?person a/rdfs:subClassOf* :Person }
                    OPTIONAL { ?person :hasName ?name }
                }
                OPTIONAL { ?person :hasAge ?age }
                OPTIONAL { ?person :hasEmail ?email }
                OPTIONAL { ?person :hasPhoneNumber ?phoneNumber }
                OPTIONAL { ?person :hasRole ?role }
                BIND(
                    IF(EXISTS { ?person rdf:type :Conducteur }, "Conducteur",
                    IF(EXISTS { ?person rdf:type :Contrôleur }, "Contrôleur",
                    IF(EXISTS { ?person rdf:type :EmployéAgence }, "EmployéAgence",
                    IF(EXISTS { ?person rdf:type :Passager }, "Passager", "Person"))))
                    AS ?type)
            }
            ORDER BY ?name
            LIMIT 100
            """
            result = sparql_query(sparql)
            ontology_persons = result.get('results', {}).get('bindings', [])
            print(f"[DEBUG] Personnes de l'ontologie: {len(ontology_persons)} trouvées")
            if ontology_persons:
                print(f"[DEBUG] Première personne: {ontology_persons[0]}")
        except Exception as e:
            print(f"[ERROR] Erreur lors de la récupération des personnes de l'ontologie: {e}")
            import traceback
            traceback.print_exc()
            messages.warning(request, f"Impossible de charger les données de l'ontologie: {e}")

    return render(request, 'list_persons.html', {
        'persons': persons,
        'ontology_persons': ontology_persons,
        'ontology_available': ONTOLOGY_AVAILABLE
    })


def create_person(request):
    """Create a new person"""
    if request.method == 'POST':
        # Debug: afficher les données POST
        print(f"[DEBUG] POST data: {request.POST}")
        print(f"[DEBUG] has_id: {request.POST.get('has_id')}")
        print(f"[DEBUG] has_name: {request.POST.get('has_name')}")
        
        form = PersonForm(request.POST)
        
        # Appeler is_valid() explicitement
        is_valid = form.is_valid()
        
        print(f"[DEBUG] Form is valid: {is_valid}")
        print(f"[DEBUG] Form errors: {form.errors}")
        if hasattr(form, 'cleaned_data'):
            print(f"[DEBUG] Cleaned data keys: {list(form.cleaned_data.keys())}")
            print(f"[DEBUG] has_id in cleaned_data: {'has_id' in form.cleaned_data}, value: {repr(form.cleaned_data.get('has_id'))}")
            print(f"[DEBUG] has_name in cleaned_data: {'has_name' in form.cleaned_data}, value: {repr(form.cleaned_data.get('has_name'))}")
        
        if is_valid:
            try:
                person = form.save()
                
                # Sync to ontology if available
                if ONTOLOGY_AVAILABLE:
                    try:
                        sync_service = OntologySyncService()
                        sync_service.sync_person_to_ontology(person)
                        messages.success(request, "Personne créée et synchronisée avec l'ontologie !")
                    except Exception as e:
                        messages.warning(request, f"Personne créée mais erreur de synchronisation: {e}")
                else:
                    messages.success(request, "Personne créée avec succès !")
                
                return redirect('list_persons')
            except Exception as e:
                messages.error(request, f"Erreur lors de la sauvegarde: {e}")
                # Afficher les erreurs du formulaire
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            # Afficher les erreurs de validation
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = PersonForm()
    return render(request, 'person_form.html', {'form': form, 'title': 'Créer une Personne'})


def update_person(request, pk):
    """Update an existing person"""
    person = get_object_or_404(Person, pk=pk)
    # Récupérer l'instance de la sous-classe
    person = Person.get_subclass(pk)
    
    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            try:
                person = form.save()
                
                # Sync to ontology if available
                if ONTOLOGY_AVAILABLE:
                    try:
                        sync_service = OntologySyncService()
                        sync_service.sync_person_to_ontology(person)
                        messages.success(request, "Personne modifiée et synchronisée !")
                    except Exception as e:
                        messages.warning(request, f"Personne modifiée mais erreur de synchronisation: {e}")
                else:
                    messages.success(request, "Personne modifiée !")
                
                return redirect('list_persons')
            except Exception as e:
                messages.error(request, f"Erreur: {e}")
    else:
        form = PersonForm(instance=person)
    
    return render(request, 'person_form.html', {
        'form': form,
        'title': 'Modifier la Personne'
    })


def delete_person(request, pk):
    """Delete a person"""
    person = get_object_or_404(Person, pk=pk)
    # Récupérer l'instance de la sous-classe
    person = Person.get_subclass(pk)
    
    if request.method == 'POST':
        # Delete from ontology first if available
        if ONTOLOGY_AVAILABLE:
            try:
                sync_service = OntologySyncService()
                sync_service.delete_person_from_ontology(person)
            except Exception as e:
                messages.warning(request, f"Erreur lors de la suppression de l'ontologie: {e}")
        
        # Then delete from database
        person.delete()
        messages.success(request, "Personne supprimée.")
        return redirect('list_persons')
    
    return render(request, 'confirm_delete.html', {
        'object': person,
        'type': 'personne'
    })


def person_ai_query(request):
    """Handle AI Query requests for persons"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)
    from .utils.ai_nl_interface import ai_generate_and_execute
    payload = request.POST.dict()
    q = payload.get('query') or payload.get('q') or ''
    res = ai_generate_and_execute(q)
    return JsonResponse(res, status=200 if 'error' not in res else 400)