import re
from core.utils.nl_to_sparql import nl_to_sparql, nl_to_sparql_update
from core.utils.fuseki import sparql_query, sparql_update
from transport_app.services.ontology_service import OntologySyncService
from transport_app.models import (
    Person, Conducteur, Contrôleur, EmployéAgence, Passager
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
    """Extract person type from filter query"""
    t = (text or "").lower()
    # Détecter les types de personnes dans la requête
    if re.search(r"\b(conducteur|driver|chauffeur)\b", t):
        return "Conducteur"
    if re.search(r"\b(contrôleur|controleur|controller|inspector)\b", t):
        return "Contrôleur"
    if re.search(r"\b(employé\s*agence|employe\s*agence|employee|agence)\b", t):
        return "EmployéAgence"
    if re.search(r"\b(passager|passenger|passenger)\b", t):
        return "Passager"
    return None


def ai_generate_and_execute(nl_text: str):
    if not nl_text or not nl_text.strip():
        return {"error": "Empty query"}
    intent = detect_intent(nl_text)
    
    if intent == 'create':
        try:
            payload = infer_create_payload(nl_text)
            print(f"[AI] Creating person with payload: {payload}")
            person = create_person(payload)
            print(f"[AI] Person created successfully: ID={person.id}, has_id={person.has_id}")
            person.refresh_from_db()
            verify_person = Person.objects.filter(has_id=person.has_id).first()
            if not verify_person:
                raise ValueError(f"Person {person.has_id} was not found in Django after creation")
            print(f"[AI] Person verified in Django: {verify_person.id}")
            return {"ok": True, "mode": "create", "created_id": person.has_id, "django_id": person.id, "debug": f"Person saved in Django with ID {person.id}"}
        except Exception as e:
            import traceback
            error_msg = str(e)
            traceback.print_exc()
            return {"error": f"Create failed in Django: {error_msg}", "traceback": traceback.format_exc()}

    if intent == 'delete':
        person_id = _extract_id(nl_text)
        if person_id:
            try:
                ok = delete_person(person_id)
                if ok:
                    return {"ok": True, "mode": "update", "deleted_id": person_id}
            except Exception as e:
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
        person_id = _extract_id(nl_text)
        if person_id:
            try:
                data = infer_update_payload(nl_text)
                if data:
                    update_person(person_id, data)
                    return {"ok": True, "mode": "update", "updated_id": person_id, "data": data}
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
            return {"ok": True, "mode": "filter", "filter_type": filter_type, "message": f"Affichage des personnes de type: {filter_type}"}
        return {"ok": True, "mode": "filter", "filter_type": None, "message": "Affichage de toutes les personnes"}
    
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
    if re.search(r"\b(conducteur|driver|chauffeur)\b", t):
        person_type = 'Conducteur'
        prefix = 'C-'
    elif re.search(r"\b(contrôleur|controleur|controller|inspector)\b", t):
        person_type = 'Contrôleur'
        prefix = 'CT-'
    elif re.search(r"\b(employé\s*agence|employe\s*agence|employee|agence)\b", t):
        person_type = 'EmployéAgence'
        prefix = 'EA-'
    elif re.search(r"\b(passager|passenger)\b", t):
        person_type = 'Passager'
        prefix = 'P-'
    else:
        person_type = 'Passager'  # default
        prefix = 'P-'

    # next numeric from existing for the chosen prefix
    next_numeric = _next_numeric(prefix)
    person_id = f"{prefix}{next_numeric:04d}"
    
    # Extract name - try multiple patterns
    name = ''
    
    # Pattern 1: "name John" or "nom John" (before other keywords)
    name = _extract_text(t, r"name\s+([\w\s]+?)(?:\s+(?:age|email|phone|license|badge|zone)|$)", re.IGNORECASE)
    if not name:
        name = _extract_text(t, r"nom\s+([\w\s]+?)(?:\s+(?:âge|email|téléphone|permis|badge|zone)|$)", re.IGNORECASE)
    
    # Pattern 2: "name is John" or "nom est John"
    if not name:
        name = _extract_text(t, r"name\s*(?:is|=|:)\s*([\w\s]+?)(?:\s+(?:age|email|phone|license|badge|zone)|$)", re.IGNORECASE)
    if not name:
        name = _extract_text(t, r"nom\s*(?:est|=|:)\s*([\w\s]+?)(?:\s+(?:âge|email|téléphone|permis|badge|zone)|$)", re.IGNORECASE)
    
    # Pattern 3: "create [type] [name]" - extract name after type keyword
    if not name:
        # Try to find name after the type keyword
        type_keywords = {
            'Conducteur': r'(?:conducteur|driver|chauffeur)',
            'Contrôleur': r'(?:contrôleur|controleur|controller|inspector)',
            'EmployéAgence': r'(?:employé\s*agence|employe\s*agence|employee|agence)',
            'Passager': r'(?:passager|passenger)',
        }
        keyword_pattern = type_keywords.get(person_type, '')
        if keyword_pattern:
            # Extract everything after the type keyword until we hit age, email, phone, etc.
            name = _extract_text(t, rf'(?:create|créer|add|ajouter)\s+{keyword_pattern}\s+([\w\s]+?)(?:\s+(?:age|email|phone|license|badge|zone|position|subscription)|$)', re.IGNORECASE)
    
    # If still no name, generate a default name based on type and ID
    if not name or name.strip() == '':
        type_names = {
            'Conducteur': 'Conducteur',
            'Contrôleur': 'Contrôleur',
            'EmployéAgence': 'Employé Agence',
            'Passager': 'Passager',
        }
        default_name = f"{type_names.get(person_type, 'Personne')} {person_id}"
        name = default_name
    
    data = {
        'has_id': person_id,
        'person_type': person_type,
        'has_name': name.strip(),
        'has_age': _extract_int(t, r"age\s*(?:is|=|:)?\s*(\d+)") or _extract_int(t, r"âge\s*(?:est|=|:)?\s*(\d+)"),
        'has_email': _extract_text(t, r"email\s*(?:is|=|:)?\s*([\w@.]+)") or _extract_text(t, r"courriel\s*(?:est|=|:)?\s*([\w@.]+)"),
        'has_phone_number': _extract_text(t, r"phone\s*(?:number)?\s*(?:is|=|:)?\s*([\d\s\-+]+)") or _extract_text(t, r"téléphone\s*(?:est|=|:)?\s*([\d\s\-+]+)"),
        'has_role': _extract_text(t, r"role\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"rôle\s*(?:est|=|:)?\s*([\w\s]+)"),
    }
    
    # Conducteur specific
    if person_type == 'Conducteur':
        data['has_license_number'] = _extract_text(t, r"license\s*(?:number)?\s*(?:is|=|:)?\s*([\w\-]+)") or _extract_text(t, r"permis\s*(?:est|=|:)?\s*([\w\-]+)")
        data['has_experience_years'] = _extract_int(t, r"experience\s*(?:years)?\s*(?:is|=|:)?\s*(\d+)") or _extract_int(t, r"expérience\s*(?:années)?\s*(?:est|=|:)?\s*(\d+)")
        data['drives_line'] = _extract_text(t, r"drives\s*(?:line)?\s*(?:is|=|:)?\s*([\w\-]+)") or _extract_text(t, r"ligne\s*(?:est|=|:)?\s*([\w\-]+)")
        data['has_work_shift'] = _extract_text(t, r"work\s*(?:shift)?\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"tranche\s*(?:horaire)?\s*(?:est|=|:)?\s*([\w\s]+)")
    
    # Contrôleur specific
    elif person_type == 'Contrôleur':
        data['has_badge_id'] = _extract_text(t, r"badge\s*(?:id)?\s*(?:is|=|:)?\s*([\w\-]+)")
        data['has_assigned_zone'] = _extract_text(t, r"zone\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"zone\s*(?:assignée)?\s*(?:est|=|:)?\s*([\w\s]+)")
        data['has_inspection_count'] = _extract_int(t, r"inspection\s*(?:count)?\s*(?:is|=|:)?\s*(\d+)") or _extract_int(t, r"inspections\s*(?:est|=|:)?\s*(\d+)")
        data['works_for_company'] = _extract_text(t, r"works\s*(?:for)?\s*(?:company)?\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"travaille\s*(?:pour)?\s*(?:est|=|:)?\s*([\w\s]+)")
    
    # EmployéAgence specific
    elif person_type == 'EmployéAgence':
        data['has_employee_id'] = _extract_text(t, r"employee\s*(?:id)?\s*(?:is|=|:)?\s*([\w\-]+)") or _extract_text(t, r"numéro\s*(?:employé)?\s*(?:est|=|:)?\s*([\w\-]+)")
        data['has_position'] = _extract_text(t, r"position\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"poste\s*(?:est|=|:)?\s*([\w\s]+)")
        data['works_at'] = _extract_text(t, r"works\s*(?:at)?\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"travaille\s*(?:à)?\s*(?:est|=|:)?\s*([\w\s]+)")
    
    # Passager specific
    elif person_type == 'Passager':
        data['has_subscription_type'] = _extract_text(t, r"subscription\s*(?:type)?\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"abonnement\s*(?:est|=|:)?\s*([\w\s]+)")
        data['has_preferred_transport'] = _extract_text(t, r"preferred\s*(?:transport)?\s*(?:is|=|:)?\s*([\w\s]+)") or _extract_text(t, r"transport\s*(?:préféré)?\s*(?:est|=|:)?\s*([\w\s]+)")
    
    return data


def _next_numeric(prefix: str):
    """Get next numeric ID for a prefix"""
    all_persons = Person.objects.all()
    max_num = -1
    for person in all_persons:
        pid = (person.has_id or '').upper()
        if pid.startswith(prefix.upper()):
            try:
                num_str = pid[len(prefix):].lstrip('-').lstrip('_')
                num = int(num_str) if num_str.isdigit() else 0
                if num > max_num:
                    max_num = num
            except Exception:
                continue
    return (max_num + 1) if max_num >= 0 else 1


def _extract_text(t: str, pattern: str, flags=0):
    m = re.search(pattern, t, flags)
    if not m:
        return ''
    # Get the first capturing group
    if m.lastindex and m.lastindex >= 1:
        return m.group(1).strip()
    return ''


def _extract_int(t: str, pattern: str):
    m = re.search(pattern, t)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _extract_id(text: str) -> str:
    t = (text or '').strip()
    # Match P-*, C-*, CT-*, EA-*, etc.
    m = re.search(r"\b(P-|C-|CT-|EA-)\d+\b", t, flags=re.IGNORECASE)
    return m.group(1).upper() if m else ''


def infer_update_payload(text: str):
    t = (text or '').lower()
    data = {}
    
    # Common fields
    name = _extract_text(t, r"name\s*(?:to|=|:)\s*([\w\s]+)") or _extract_text(t, r"nom\s*(?:to|=|:)\s*([\w\s]+)")
    if name: data['has_name'] = name
    
    age = _extract_int(t, r"age\s*(?:to|=|:)\s*(\d+)") or _extract_int(t, r"âge\s*(?:to|=|:)\s*(\d+)")
    if age: data['has_age'] = age
    
    email = _extract_text(t, r"email\s*(?:to|=|:)\s*([\w@.]+)") or _extract_text(t, r"courriel\s*(?:to|=|:)\s*([\w@.]+)")
    if email: data['has_email'] = email
    
    phone = _extract_text(t, r"phone\s*(?:number)?\s*(?:to|=|:)\s*([\d\s\-+]+)") or _extract_text(t, r"téléphone\s*(?:to|=|:)\s*([\d\s\-+]+)")
    if phone: data['has_phone_number'] = phone
    
    role = _extract_text(t, r"role\s*(?:to|=|:)\s*([\w\s]+)") or _extract_text(t, r"rôle\s*(?:to|=|:)\s*([\w\s]+)")
    if role: data['has_role'] = role
    
    return data


def create_person(data: dict):
    """Create a person in Django and sync to ontology"""
    person_type = data.pop('person_type', 'Passager')
    
    model_map = {
        'Conducteur': Conducteur,
        'Contrôleur': Contrôleur,
        'EmployéAgence': EmployéAgence,
        'Passager': Passager,
    }
    
    model = model_map.get(person_type, Passager)
    
    # Remove None values and empty strings
    clean_data = {k: v for k, v in data.items() if v is not None and v != ''}
    
    # Ensure has_id is present
    if 'has_id' not in clean_data or not clean_data['has_id']:
        raise ValueError("has_id is required")
    
    # Ensure has_name is present
    if 'has_name' not in clean_data or not clean_data['has_name']:
        raise ValueError("has_name is required")
    
    print(f"[create_person] Creating {person_type} with data: {clean_data}")
    
    try:
        person = model(**clean_data)
        person.full_clean()
        person.save()
        print(f"[create_person] Person saved successfully: ID={person.id}, has_id={person.has_id}")
        
        # Sync to ontology
        try:
            sync_service = OntologySyncService()
            sync_service.sync_person_to_ontology(person)
            print(f"[create_person] Person synced to ontology")
        except Exception as sync_error:
            print(f"[create_person] WARNING: Failed to sync to ontology: {sync_error}")
        
        return person
    except Exception as e:
        print(f"[create_person] ERROR creating person: {e}")
        import traceback
        traceback.print_exc()
        raise


def update_person(person_id: str, data: dict):
    """Update a person in Django and sync to ontology"""
    try:
        person = Person.objects.get(has_id=person_id)
        
        # Remove None values
        clean_data = {k: v for k, v in data.items() if v is not None}
        
        for key, value in clean_data.items():
            setattr(person, key, value)
        
        person.full_clean()
        person.save()
        
        # Sync to ontology
        try:
            sync_service = OntologySyncService()
            sync_service.sync_person_to_ontology(person)
        except Exception as sync_error:
            print(f"[update_person] WARNING: Failed to sync to ontology: {sync_error}")
        
        return person
    except Person.DoesNotExist:
        raise ValueError(f"Person with ID {person_id} not found")
    except Exception as e:
        print(f"[update_person] ERROR updating person: {e}")
        raise


def delete_person(person_id: str):
    """Delete a person from Django and ontology"""
    try:
        person = Person.objects.get(has_id=person_id)
        
        # Delete from ontology first
        try:
            sync_service = OntologySyncService()
            sync_service.delete_person_from_ontology(person)
        except Exception as sync_error:
            print(f"[delete_person] WARNING: Failed to delete from ontology: {sync_error}")
        
        # Delete from Django
        person.delete()
        return True
    except Person.DoesNotExist:
        raise ValueError(f"Person with ID {person_id} not found")
    except Exception as e:
        print(f"[delete_person] ERROR deleting person: {e}")
        raise

