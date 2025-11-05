import re
from core.utils.nl_to_sparql import nl_to_sparql, nl_to_sparql_update
from core.utils.fuseki import sparql_query, sparql_update
from transport_app.services.ontology_service import OntologySyncService
from ticket_app.models import (
    Ticket, TicketSimple, TicketSenior, TicketÉtudiant,
    AbonnementHebdomadaire, AbonnementMensuel
)


def is_update_query(sparql_text: str) -> bool:
    txt = (sparql_text or "").strip().upper()
    return any(k in txt for k in ["INSERT", "DELETE", "WITH", "DELETE DATA", "INSERT DATA"]) and "SELECT" not in txt


def detect_intent(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\b(delete|remove|supprimer|effacer|drop)\b", t):
        return "delete"
    if re.search(r"\b(update|modify|change|edit|mettre\s+à\s+jour|changer|modifier)\b", t):
        return "update"
    if re.search(r"\b(create|add|insert|ajouter|créer)\b", t):
        return "create"
    # Détecter les requêtes de liste/filtrage
    if re.search(r"\b(list|show|display|afficher|voir|lister)\b", t):
        return "filter"
    return "read"


def extract_filter_type(text: str) -> str:
    """Extract ticket type from filter query"""
    t = (text or "").lower()
    # Détecter les types de tickets dans la requête
    if re.search(r"\b(ticket\s*simple|simple\s*ticket)\b", t):
        return "TicketSimple"
    if re.search(r"\b(ticket\s*senior|senior\s*ticket)\b", t):
        return "TicketSenior"
    if re.search(r"\b(ticket\s*étudiant|ticket\s*etudiant|étudiant\s*ticket|etudiant\s*ticket|student\s*ticket)\b", t):
        return "TicketÉtudiant"
    if re.search(r"\b(abonnement\s*hebdomadaire|hebdomadaire|weekly)\b", t):
        return "AbonnementHebdomadaire"
    if re.search(r"\b(abonnement\s*mensuel|mensuel|monthly)\b", t):
        return "AbonnementMensuel"
    return None


def ai_generate_and_execute(nl_text: str):
    if not nl_text or not nl_text.strip():
        return {"error": "Empty query"}
    intent = detect_intent(nl_text)
    
    if intent == 'create':
        try:
            payload = infer_create_payload(nl_text)
            print(f"[AI] Creating ticket with payload: {payload}")  # Debug
            ticket = create_ticket(payload)
            print(f"[AI] Ticket created successfully: ID={ticket.id}, has_ticket_id={ticket.has_ticket_id}")  # Debug
            # S'assurer que le ticket est bien sauvegardé avant de retourner
            ticket.refresh_from_db()
            # Vérifier que le ticket existe bien dans Django
            verify_ticket = Ticket.objects.filter(has_ticket_id=ticket.has_ticket_id).first()
            if not verify_ticket:
                raise ValueError(f"Ticket {ticket.has_ticket_id} was not found in Django after creation")
            print(f"[AI] Ticket verified in Django: {verify_ticket.id}")  # Debug
            return {"ok": True, "mode": "create", "created_id": ticket.has_ticket_id, "django_id": ticket.id, "debug": f"Ticket saved in Django with ID {ticket.id}"}
        except Exception as e:
            import traceback
            error_msg = str(e)
            traceback.print_exc()  # Debug
            # Ne pas faire de fallback - si Django échoue, on retourne l'erreur
            return {"error": f"Create failed in Django: {error_msg}", "traceback": traceback.format_exc()}

    if intent == 'delete':
        ticket_id = _extract_id(nl_text)
        if ticket_id:
            try:
                ok = delete_ticket(ticket_id)
                if ok:
                    return {"ok": True, "mode": "update", "deleted_id": ticket_id}
            except Exception as e:
                # fallback if canonical delete fails
                pass
        # fallback to AI SPARQL
        u = nl_to_sparql_update(nl_text)
        if not u:
            return {"error": "AI failed to generate DELETE"}
        try:
            sparql_update(u)
            return {"ok": True, "mode": "update", "sparql": u}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": u}

    if intent == 'update':
        ticket_id = _extract_id(nl_text)
        if ticket_id:
            try:
                # Build partial data from NL
                data = infer_update_payload(nl_text)
                if data:
                    update_ticket(ticket_id, data)
                    return {"ok": True, "mode": "update", "updated_id": ticket_id, "data": data}
            except Exception:
                pass
        # fallback to AI SPARQL
        u = nl_to_sparql_update(nl_text)
        if not u:
            return {"error": "AI failed to generate UPDATE SPARQL"}
        try:
            sparql_update(u)
            return {"ok": True, "mode": "update", "sparql": u}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": u}

    # filter (list with type filter)
    if intent == 'filter':
        filter_type = extract_filter_type(nl_text)
        if filter_type:
            return {"ok": True, "mode": "filter", "filter_type": filter_type, "message": f"Affichage des tickets de type: {filter_type}"}
        # Si pas de type spécifique, juste recharger la liste complète
        return {"ok": True, "mode": "filter", "filter_type": None, "message": "Affichage de tous les tickets"}
    
    # read
    s = nl_to_sparql(nl_text)
    if not s:
        return {"error": "AI failed to generate SPARQL"}
    if is_update_query(s):
        try:
            sparql_update(s)
            return {"ok": True, "mode": "update", "sparql": s}
        except Exception as e:
            return {"error": str(e), "mode": "update", "sparql": s}
    try:
        res = sparql_query(s)
        return {"ok": True, "mode": "select", "sparql": s, "results": res}
    except Exception as e:
        return {"error": str(e), "mode": "select", "sparql": s}


def infer_create_payload(text: str):
    t = (text or '').lower()
    # detect type for ID prefix
    if re.search(r"\b(simple|basique|standard)\b", t):
        ticket_type = 'TicketSimple'
        prefix = 'T-S-'
    elif re.search(r"\b(senior|sénior)\b", t):
        ticket_type = 'TicketSenior'
        prefix = 'T-SR-'
    elif re.search(r"\b(étudiant|etudiant|student|étudiant)\b", t):
        ticket_type = 'TicketÉtudiant'
        prefix = 'T-E-'
    elif re.search(r"\b(hebdomadaire|weekly|semaine)\b", t):
        ticket_type = 'AbonnementHebdomadaire'
        prefix = 'A-H-'
    elif re.search(r"\b(mensuel|monthly|mois)\b", t):
        ticket_type = 'AbonnementMensuel'
        prefix = 'A-M-'
    else:
        ticket_type = 'TicketSimple'  # default
        prefix = 'T-'

    # next numeric from existing for the chosen prefix
    next_numeric = _next_numeric(prefix)
    if prefix == 'T-':
        # Format: T-0001, T-0011, etc.
        ticket_id = f"{prefix}{next_numeric:04d}"
    else:
        # Format: T-S-0001, A-M-0001, etc.
        ticket_id = f"{prefix}{next_numeric:04d}"
    
    # Try to find person and transport from the query
    from transport_app.models import Person, Transport, Bus, Metro, Train, Tram
    
    owned_by = None
    # Look for person name or ID in the query
    person_name_match = re.search(r"\b(?:owned\s*by|pour|owner)\s+([\w\s]+)", t)
    if person_name_match:
        person_name = person_name_match.group(1).strip()
        try:
            owned_by = Person.objects.filter(has_name__icontains=person_name).first()
        except Exception:
            pass
    
    valid_for = None
    # Look for transport line number or type in the query
    transport_match = re.search(r"\b(?:valid\s*for|transport|bus|metro|train|tram)\s+([\w\-]+)", t)
    if transport_match:
        transport_line = transport_match.group(1).strip()
        try:
            # Try to find in all transport types
            for model in [Bus, Metro, Train, Tram]:
                valid_for = model.objects.filter(transport_line_number__icontains=transport_line).first()
                if valid_for:
                    break
        except Exception:
            pass
    
    data = {
        'has_ticket_id': ticket_id,
        'ticket_type': ticket_type,
        'has_price': _extract_float(t, r"price\s*(?:is|=|:)?\s*([\d.]+)"),
        'has_validity_duration': _extract_text(t, r"validity\s*(?:duration)?\s*(?:is|=|:)?\s*([\w\s]+)"),
        'has_purchase_date': _extract_text(t, r"purchase\s*date\s*(?:is|=|:)?\s*([\w\-/:]+)"),
        'has_expiration_date': _extract_text(t, r"expiration\s*date\s*(?:is|=|:)?\s*([\w\-/:]+)"),
        'is_reduced_fare': bool(re.search(r"\b(reduced|réduit|tarif\s+réduit)\b", t)),
        'owned_by': owned_by,
        'valid_for': valid_for,
        # TicketSimple specific
        'is_used': bool(re.search(r"\b(used|utilisé|utilisé)\b", t)) if ticket_type == 'TicketSimple' else None,
        # TicketSenior specific
        'has_age_condition': _extract_int(t, r"age\s*(?:condition)?\s*(?:is|=|:)?\s*(\d+)") if ticket_type == 'TicketSenior' else None,
        # TicketÉtudiant specific
        'has_institution_name': _extract_text(t, r"institution\s*(?:name)?\s*(?:is|=|:)?\s*([\w\s]+)") if ticket_type == 'TicketÉtudiant' else None,
        'has_student_id': _extract_text(t, r"student\s*id\s*(?:is|=|:)?\s*([\w\-]+)") if ticket_type == 'TicketÉtudiant' else None,
        # AbonnementHebdomadaire specific
        'has_start_date': _extract_text(t, r"start\s*date\s*(?:is|=|:)?\s*([\w\-/:]+)") if ticket_type == 'AbonnementHebdomadaire' else None,
        'has_end_date': _extract_text(t, r"end\s*date\s*(?:is|=|:)?\s*([\w\-/:]+)") if ticket_type == 'AbonnementHebdomadaire' else None,
        'has_zone_access': _extract_text(t, r"zone\s*(?:access)?\s*(?:is|=|:)?\s*([\w\s]+)") if ticket_type == 'AbonnementHebdomadaire' else None,
        # AbonnementMensuel specific
        'has_month': _extract_text(t, r"month\s*(?:is|=|:)?\s*([\w\-]+)") if ticket_type == 'AbonnementMensuel' else None,
        'has_auto_renewal': bool(re.search(r"\b(auto\s*renewal|renouvellement\s*auto)\b", t)) if ticket_type == 'AbonnementMensuel' else None,
        'has_payment_method': _extract_text(t, r"payment\s*(?:method)?\s*(?:is|=|:)?\s*([\w\s]+)") if ticket_type == 'AbonnementMensuel' else None,
    }
    return data


def _next_numeric(prefix: str):
    """Get next numeric ID for a prefix"""
    all_tickets = Ticket.objects.all()
    max_num = -1
    for ticket in all_tickets:
        tid = (ticket.has_ticket_id or '').upper()
        if tid.startswith(prefix.upper()):
            try:
                # Extract number after prefix (handle formats like T-001, T-S-001, etc.)
                num_str = tid[len(prefix):].lstrip('-').lstrip('_')
                # Remove leading zeros but keep numeric part
                num = int(num_str) if num_str.isdigit() else 0
                if num > max_num:
                    max_num = num
            except Exception:
                continue
    return (max_num + 1) if max_num >= 0 else 1


def _extract_text(t: str, pattern: str):
    m = re.search(pattern, t)
    if not m:
        return ''
    return (m.group(1) if m.lastindex == 1 else m.group(2)).strip()


def _extract_int(t: str, pattern: str):
    m = re.search(pattern, t)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _extract_float(t: str, pattern: str):
    m = re.search(pattern, t)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _extract_id(text: str) -> str:
    t = (text or '').strip()
    # Match T-*, A-*, T-S-*, etc.
    m = re.search(r"\b(T-[A-Z]?-\d+|A-[A-Z]-\d+|T-\d+|T-\w+-\d+)\b", t, flags=re.IGNORECASE)
    return m.group(1).upper() if m else ''


def infer_update_payload(text: str):
    t = (text or '').lower()
    data = {}
    
    # Common fields
    price = _extract_float(t, r"price\s*(?:to|=|:)\s*([\d.]+)")
    if price: data['has_price'] = price
    
    vd = _extract_text(t, r"validity\s*(?:duration)?\s*(?:to|=|:)\s*([\w\s]+)")
    if vd: data['has_validity_duration'] = vd
    
    pd = _extract_text(t, r"purchase\s*date\s*(?:to|=|:)\s*([\w\-/:]+)")
    if pd: data['has_purchase_date'] = pd
    
    ed = _extract_text(t, r"expiration\s*date\s*(?:to|=|:)\s*([\w\-/:]+)")
    if ed: data['has_expiration_date'] = ed
    
    if re.search(r"\b(reduced|réduit|tarif\s+réduit)\b", t):
        data['is_reduced_fare'] = True
    
    # TicketSimple
    if re.search(r"\b(used|utilisé)\b", t):
        data['is_used'] = True
    if re.search(r"\b(not\s*used|non\s*utilisé)\b", t):
        data['is_used'] = False
    
    # TicketSenior
    age = _extract_int(t, r"age\s*(?:condition)?\s*(?:to|=|:)\s*(\d+)")
    if age: data['has_age_condition'] = age
    
    # TicketÉtudiant
    inst = _extract_text(t, r"institution\s*(?:name)?\s*(?:to|=|:)\s*([\w\s]+)")
    if inst: data['has_institution_name'] = inst
    sid = _extract_text(t, r"student\s*id\s*(?:to|=|:)\s*([\w\-]+)")
    if sid: data['has_student_id'] = sid
    
    # AbonnementHebdomadaire
    sd = _extract_text(t, r"start\s*date\s*(?:to|=|:)\s*([\w\-/:]+)")
    if sd: data['has_start_date'] = sd
    ed = _extract_text(t, r"end\s*date\s*(?:to|=|:)\s*([\w\-/:]+)")
    if ed: data['has_end_date'] = ed
    za = _extract_text(t, r"zone\s*(?:access)?\s*(?:to|=|:)\s*([\w\s]+)")
    if za: data['has_zone_access'] = za
    
    # AbonnementMensuel
    month = _extract_text(t, r"month\s*(?:to|=|:)\s*([\w\-]+)")
    if month: data['has_month'] = month
    if re.search(r"\b(auto\s*renewal|renouvellement\s*auto)\b", t):
        data['has_auto_renewal'] = True
    pm = _extract_text(t, r"payment\s*(?:method)?\s*(?:to|=|:)\s*([\w\s]+)")
    if pm: data['has_payment_method'] = pm
    
    return data


def create_ticket(data: dict):
    """Create a ticket in Django and sync to ontology"""
    ticket_type = data.pop('ticket_type', 'TicketSimple')
    
    model_map = {
        'TicketSimple': TicketSimple,
        'TicketSenior': TicketSenior,
        'TicketÉtudiant': TicketÉtudiant,
        'AbonnementHebdomadaire': AbonnementHebdomadaire,
        'AbonnementMensuel': AbonnementMensuel,
    }
    
    model = model_map.get(ticket_type, TicketSimple)
    
    # Remove None values and empty strings
    clean_data = {k: v for k, v in data.items() if v is not None and v != ''}
    
    # Ensure has_ticket_id is present
    if 'has_ticket_id' not in clean_data or not clean_data['has_ticket_id']:
        raise ValueError("has_ticket_id is required")
    
    print(f"[create_ticket] Creating {ticket_type} with data: {clean_data}")  # Debug
    
    try:
        ticket = model(**clean_data)
        ticket.full_clean()  # Validate before saving
        ticket.save()
        print(f"[create_ticket] Ticket saved successfully: ID={ticket.id}, has_ticket_id={ticket.has_ticket_id}")  # Debug
        
        # Sync to ontology
        try:
            sync_service = OntologySyncService()
            sync_service.sync_ticket_to_ontology(ticket)
            print(f"[create_ticket] Ticket synced to ontology")  # Debug
        except Exception as sync_error:
            print(f"[create_ticket] WARNING: Failed to sync to ontology: {sync_error}")  # Debug
            # Continue even if sync fails - ticket is in Django
        
        return ticket
    except Exception as e:
        print(f"[create_ticket] ERROR creating ticket: {e}")  # Debug
        import traceback
        traceback.print_exc()
        raise


def update_ticket(ticket_id: str, data: dict):
    """Update a ticket in Django and sync to ontology"""
    try:
        ticket = Ticket.objects.get(has_ticket_id=ticket_id)
        
        # Remove None values
        clean_data = {k: v for k, v in data.items() if v is not None}
        
        for key, value in clean_data.items():
            setattr(ticket, key, value)
        
        ticket.save()
        
        # Sync to ontology
        sync_service = OntologySyncService()
        sync_service.sync_ticket_to_ontology(ticket)
        
        return ticket
    except Ticket.DoesNotExist:
        raise Exception(f"Ticket {ticket_id} not found")


def delete_ticket(ticket_id: str):
    """Delete a ticket from Django and ontology"""
    try:
        ticket = Ticket.objects.get(has_ticket_id=ticket_id)
        
        # Delete from ontology first
        sync_service = OntologySyncService()
        sync_service.delete_ticket_from_ontology(ticket)
        
        # Then delete from Django
        ticket.delete()
        
        return True
    except Ticket.DoesNotExist:
        raise Exception(f"Ticket {ticket_id} not found")

