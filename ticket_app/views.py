from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse

from .models import (
    Ticket, TicketSimple, TicketSenior, TicketÉtudiant,
    AbonnementHebdomadaire, AbonnementMensuel
)
from .forms import TicketForm
from .utils.ai_nl_interface import ai_generate_and_execute

# Import des services ontologie
try:
    from transport_app.services.ontology_service import OntologySyncService
    from core.utils.fuseki import sparql_query
    ONTOLOGY_AVAILABLE = True
except ImportError as e:
    print(f"Ontology services not available: {e}")
    ONTOLOGY_AVAILABLE = False


# ==================== TICKETS ====================

def list_tickets(request):
    """List all tickets grouped by type"""
    tickets = []
    for subclass in Ticket.__subclasses__():
        qs = subclass.objects.all().order_by('-id')  # Plus récent en premier
        for obj in qs:
            obj.ticket_type = subclass.__name__
            tickets.append(obj)
    
    # Trier par ID décroissant pour avoir les plus récents en premier
    tickets.sort(key=lambda x: x.id, reverse=True)
    
    # Query ontology for additional ticket data
    ontology_tickets = []
    if ONTOLOGY_AVAILABLE:
        try:
            sparql = """
            PREFIX : <http://www.transport-ontology.org/travel#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            
            SELECT ?ticket ?id ?price ?purchaseDate ?type
            WHERE {
                ?ticket a/rdfs:subClassOf* :Ticket ;
                        :hasTicketID ?id .
                OPTIONAL { ?ticket :hasPrice ?price }
                OPTIONAL { ?ticket :hasPurchaseDate ?purchaseDate }
                BIND(
                    IF(EXISTS { ?ticket rdf:type :TicketSimple }, "TicketSimple",
                    IF(EXISTS { ?ticket rdf:type :TicketSenior }, "TicketSenior",
                    IF(EXISTS { ?ticket rdf:type :TicketEtudiant }, "TicketEtudiant",
                    IF(EXISTS { ?ticket rdf:type :AbonnementHebdomadaire }, "AbonnementHebdomadaire",
                    IF(EXISTS { ?ticket rdf:type :AbonnementMensuel }, "AbonnementMensuel", "Ticket")))))
                    AS ?type)
            }
            LIMIT 50
            """
            result = sparql_query(sparql)
            ontology_tickets = result.get('results', {}).get('bindings', [])
        except Exception as e:
            messages.warning(request, f"Impossible de charger les données de l'ontologie: {e}")

    return render(request, 'ticket_app/list_tickets.html', {
        'tickets': tickets,
        'ontology_tickets': ontology_tickets,
        'ontology_available': ONTOLOGY_AVAILABLE
    })


def create_ticket(request):
    """Create a new ticket"""
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            try:
                ticket = form.save()
                
                # Sync to ontology if available
                if ONTOLOGY_AVAILABLE:
                    try:
                        sync_service = OntologySyncService()
                        sync_service.sync_ticket_to_ontology(ticket)
                        messages.success(request, "Ticket créé et synchronisé avec l'ontologie !")
                    except Exception as e:
                        messages.warning(request, f"Ticket créé mais erreur de synchronisation: {e}")
                else:
                    messages.success(request, "Ticket créé avec succès !")
                
                return redirect('list_tickets')
            except Exception as e:
                messages.error(request, f"Erreur lors de la sauvegarde: {e}")
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = TicketForm()
    return render(request, 'ticket_app/ticket_form.html', {'form': form, 'title': 'Créer un Ticket'})


def update_ticket(request, pk):
    """Update an existing ticket"""
    ticket = get_object_or_404(Ticket, pk=pk)
    # Récupérer l'instance de la sous-classe
    ticket = Ticket.get_subclass(pk)
    
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            try:
                ticket = form.save()
                
                # Sync to ontology if available
                if ONTOLOGY_AVAILABLE:
                    try:
                        sync_service = OntologySyncService()
                        sync_service.sync_ticket_to_ontology(ticket)
                        messages.success(request, "Ticket modifié et synchronisé !")
                    except Exception as e:
                        messages.warning(request, f"Ticket modifié mais erreur de synchronisation: {e}")
                else:
                    messages.success(request, "Ticket modifié !")
                
                return redirect('list_tickets')
            except Exception as e:
                messages.error(request, f"Erreur: {e}")
    else:
        form = TicketForm(instance=ticket)
    
    return render(request, 'ticket_app/ticket_form.html', {
        'form': form,
        'title': 'Modifier le Ticket'
    })


def delete_ticket(request, pk):
    """Delete a ticket"""
    ticket = get_object_or_404(Ticket, pk=pk)
    # Récupérer l'instance de la sous-classe
    ticket = Ticket.get_subclass(pk)
    
    if request.method == 'POST':
        # Delete from ontology first if available
        if ONTOLOGY_AVAILABLE:
            try:
                sync_service = OntologySyncService()
                sync_service.delete_ticket_from_ontology(ticket)
            except Exception as e:
                messages.warning(request, f"Erreur lors de la suppression de l'ontologie: {e}")
        
        # Then delete from database
        ticket.delete()
        messages.success(request, "Ticket supprimé.")
        return redirect('list_tickets')
    
    return render(request, 'ticket_app/confirm_delete.html', {
        'object': ticket,
        'type': 'ticket'
    })


def ticket_ai_query(request):
    """Handle AI Query requests for tickets"""
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)
    payload = request.POST.dict()
    q = payload.get('query') or payload.get('q') or ''
    res = ai_generate_and_execute(q)
    return JsonResponse(res, status=200 if 'error' not in res else 400)

