# ticket_app/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Ticket, TicketSimple, TicketSenior, TicketÉtudiant,
    AbonnementHebdomadaire, AbonnementMensuel
)
from transport_app.models import Person, Transport, Bus, Metro, Train, Tram

# Import pour les requêtes ontologie
try:
    from core.utils.fuseki import sparql_query
    ONTOLOGY_AVAILABLE = True
except ImportError:
    ONTOLOGY_AVAILABLE = False


class TicketForm(forms.ModelForm):
    ticket_type = forms.ChoiceField(
        choices=[
            ('ticketsimple', 'Ticket Simple'),
            ('ticketsenior', 'Ticket Senior'),
            ('ticketétudiant', 'Ticket Étudiant'),
            ('abonnementhebdomadaire', 'Abonnement Hebdomadaire'),
            ('abonnementmensuel', 'Abonnement Mensuel'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'ticket_type'}),
        label="Type de ticket"
    )

    # Champs communs à tous les Tickets
    has_ticket_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'T-001, T-002, etc.', 'class': 'form-control'}),
        label="ID du Ticket",
        help_text="Identifiant unique du ticket (obligatoire)",
        strip=True
    )
    has_price = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
        label="Prix"
    )
    has_validity_duration = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '1 jour, 1 semaine, etc.', 'class': 'form-control'}),
        label="Durée de validité"
    )
    has_purchase_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Date d'achat"
    )
    has_expiration_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Date d'expiration"
    )
    is_reduced_fare = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Tarif réduit"
    )
    owned_by = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'field_owned_by'}),
        required=False,
        label="Propriétaire (Personne)"
    )
    valid_for = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'field_valid_for'}),
        required=False,
        label="Valide pour (Transport)"
    )

    # Champs spécifiques TicketSimple
    is_used = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'field_ticketsimple_used'}),
        label="Ticket utilisé"
    )

    # Champs spécifiques TicketSenior
    has_age_condition = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'field_ticketsenior_age'}),
        label="Condition d'âge minimum"
    )

    # Champs spécifiques TicketÉtudiant
    has_institution_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_ticketetudiant_institution'}),
        label="Nom de l'institution"
    )
    has_student_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_ticketetudiant_studentid'}),
        label="Numéro d'étudiant"
    )

    # Champs spécifiques AbonnementHebdomadaire
    has_start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'field_abonnementhebdomadaire_start'}),
        label="Date de début"
    )
    has_end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'field_abonnementhebdomadaire_end'}),
        label="Date de fin"
    )
    has_zone_access = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_abonnementhebdomadaire_zone'}),
        label="Zone d'accès"
    )

    # Champs spécifiques AbonnementMensuel
    has_month = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_abonnementmensuel_month'}),
        label="Mois"
    )
    has_auto_renewal = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'field_abonnementmensuel_autorenewal'}),
        label="Renouvellement automatique"
    )
    has_payment_method = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_abonnementmensuel_payment'}),
        label="Méthode de paiement"
    )

    class Meta:
        model = Ticket
        fields = []  # Tous les champs sont définis manuellement

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # === PERSONNES ===
        person_choices = [('', '— Choisir une personne —')]
        for person in Person.objects.all():
            person_choices.append((str(person.pk), f"{person.has_name} ({person.has_id})"))
        person_choices.sort(key=lambda x: x[1])
        self.fields['owned_by'].choices = person_choices

        # === TRANSPORTS - Depuis l'ontologie ===
        transport_choices = [('', '— Choisir un transport —')]
        
        # Essayer d'abord depuis l'ontologie
        if ONTOLOGY_AVAILABLE:
            try:
                sparql = """
                PREFIX : <http://www.transport-ontology.org/travel#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?transport ?line ?type
                WHERE {
                    ?transport a/rdfs:subClassOf* :Transport ;
                            :Transport_hasLineNumber ?line .
                    BIND(
                        IF(EXISTS { ?transport a :Bus }, "Bus",
                        IF(EXISTS { ?transport a :Metro }, "Metro",
                        IF(EXISTS { ?transport a :Train }, "Train",
                        IF(EXISTS { ?transport a :Tram }, "Tram", "Transport")))))
                        AS ?type)
                }
                ORDER BY ?line
                LIMIT 100
                """
                result = sparql_query(sparql)
                bindings = result.get('results', {}).get('bindings', [])
                
                # Créer un mapping URI -> Transport Django
                uri_to_transport = {}
                for binding in bindings:
                    transport_uri = binding.get('transport', {}).get('value', '')
                    line = binding.get('line', {}).get('value', '')
                    transport_type = binding.get('type', {}).get('value', 'Transport')
                    
                    if transport_uri and line:
                        # Extraire le nom du transport depuis l'URI (ex: Bus_23)
                        transport_name = transport_uri.split('#')[-1] if '#' in transport_uri else transport_uri.split('/')[-1]
                        
                        # Chercher dans la base de données Django par numéro de ligne
                        try:
                            if transport_type == 'Bus':
                                transport = Bus.objects.filter(transport_line_number=line).first()
                            elif transport_type == 'Metro':
                                transport = Metro.objects.filter(transport_line_number=line).first()
                            elif transport_type == 'Train':
                                transport = Train.objects.filter(transport_line_number=line).first()
                            elif transport_type == 'Tram':
                                transport = Tram.objects.filter(transport_line_number=line).first()
                            else:
                                # Fallback: chercher dans toutes les sous-classes
                                transport = None
                                for model in [Bus, Metro, Train, Tram]:
                                    transport = model.objects.filter(transport_line_number=line).first()
                                    if transport:
                                        break
                            
                            if transport:
                                transport_choices.append((str(transport.pk), f"{line} ({transport_type})"))
                        except Exception:
                            # Si on ne trouve pas dans Django, on utilise l'URI comme identifiant temporaire
                            transport_choices.append((transport_name, f"{line} ({transport_type})"))
                
            except Exception as e:
                print(f"[WARNING] Erreur lors de la récupération des transports depuis l'ontologie: {e}")
                # Fallback sur la base de données Django
                for model in [Bus, Metro, Train, Tram]:
                    for transport in model.objects.all():
                        transport_choices.append((str(transport.pk), f"{transport.transport_line_number} ({transport.get_type()})"))
        else:
            # Fallback sur la base de données Django si l'ontologie n'est pas disponible
            for model in [Bus, Metro, Train, Tram]:
                for transport in model.objects.all():
                    transport_choices.append((str(transport.pk), f"{transport.transport_line_number} ({transport.get_type()})"))
        
        transport_choices.sort(key=lambda x: x[1])
        self.fields['valid_for'].choices = transport_choices

        # Si on modifie une instance existante
        if self.instance and self.instance.pk:
            # Remplir les champs communs
            self.fields['has_ticket_id'].initial = self.instance.has_ticket_id
            self.fields['has_price'].initial = self.instance.has_price
            self.fields['has_validity_duration'].initial = self.instance.has_validity_duration
            self.fields['has_purchase_date'].initial = self.instance.has_purchase_date
            self.fields['has_expiration_date'].initial = self.instance.has_expiration_date
            self.fields['is_reduced_fare'].initial = self.instance.is_reduced_fare
            if self.instance.owned_by:
                self.fields['owned_by'].initial = str(self.instance.owned_by.pk)
            if self.instance.valid_for:
                self.fields['valid_for'].initial = str(self.instance.valid_for.pk)

            # Déterminer le type et remplir les champs spécifiques
            if isinstance(self.instance, TicketSimple):
                self.fields['ticket_type'].initial = 'ticketsimple'
                self.fields['is_used'].initial = self.instance.is_used
            elif isinstance(self.instance, TicketSenior):
                self.fields['ticket_type'].initial = 'ticketsenior'
                self.fields['has_age_condition'].initial = self.instance.has_age_condition
            elif isinstance(self.instance, TicketÉtudiant):
                self.fields['ticket_type'].initial = 'ticketétudiant'
                self.fields['has_institution_name'].initial = self.instance.has_institution_name
                self.fields['has_student_id'].initial = self.instance.has_student_id
            elif isinstance(self.instance, AbonnementHebdomadaire):
                self.fields['ticket_type'].initial = 'abonnementhebdomadaire'
                self.fields['has_start_date'].initial = self.instance.has_start_date
                self.fields['has_end_date'].initial = self.instance.has_end_date
                self.fields['has_zone_access'].initial = self.instance.has_zone_access
            elif isinstance(self.instance, AbonnementMensuel):
                self.fields['ticket_type'].initial = 'abonnementmensuel'
                self.fields['has_month'].initial = self.instance.has_month
                self.fields['has_auto_renewal'].initial = self.instance.has_auto_renewal
                self.fields['has_payment_method'].initial = self.instance.has_payment_method

    def clean_owned_by(self):
        """Valider et récupérer l'objet Person"""
        value = self.cleaned_data.get('owned_by')
        if not value:
            return None
        try:
            pk = int(value)
            return Person.get_subclass(pk)
        except (ValueError, Person.DoesNotExist):
            raise ValidationError("Personne invalide.")

    def clean_valid_for(self):
        """Valider et récupérer l'objet Transport"""
        value = self.cleaned_data.get('valid_for')
        if not value:
            return None
        try:
            pk = int(value)
            return Transport.objects.get(pk=pk)
        except (ValueError, Transport.DoesNotExist):
            raise ValidationError("Transport invalide.")

    def full_clean(self):
        """Override full_clean pour forcer les valeurs et supprimer les erreurs"""
        # Appeler super().full_clean() qui appelle _clean_fields(), clean(), et _post_clean()
        super().full_clean()
        
        # S'assurer que cleaned_data existe (peut ne pas exister pour les requêtes GET)
        if not hasattr(self, 'cleaned_data'):
            self.cleaned_data = {}
        
        # APRÈS full_clean(), forcer les valeurs et supprimer les erreurs
        has_ticket_id_raw = self.data.get('has_ticket_id', '')
        
        # Gérer le cas QueryDict (liste)
        if isinstance(has_ticket_id_raw, list):
            has_ticket_id_raw = has_ticket_id_raw[0] if has_ticket_id_raw else ''
        
        # Nettoyer la valeur
        has_ticket_id = str(has_ticket_id_raw).strip() if has_ticket_id_raw else ''
        
        # FORCER les valeurs dans cleaned_data
        if has_ticket_id:
            self.cleaned_data['has_ticket_id'] = has_ticket_id
            # Supprimer l'erreur si elle existe
            if 'has_ticket_id' in self.errors:
                del self.errors['has_ticket_id']
        elif not has_ticket_id and self.data:  # Seulement si c'est une soumission de formulaire
            # Ne pas ajouter d'erreur pour les requêtes GET
            if 'has_ticket_id' not in self.cleaned_data:
                self.cleaned_data['has_ticket_id'] = ''
    
    def clean_has_ticket_id(self):
        """Valider et nettoyer has_ticket_id - TOUJOURS récupérer depuis self.data"""
        value = self.data.get('has_ticket_id', '')
        if isinstance(value, list):
            value = value[0] if value else ''
        if value:
            value = str(value).strip()
        else:
            value = ''
        
        if not value:
            raise ValidationError("Ce champ ne peut pas être vide.")
        
        return value
    
    def clean(self):
        """Validation globale du formulaire"""
        cleaned_data = super().clean()
        
        # FORCER les valeurs dans cleaned_data et supprimer les erreurs
        # Récupérer depuis self.data (toujours disponible)
        has_ticket_id_raw = self.data.get('has_ticket_id', '')
        
        # Gérer le cas QueryDict (liste)
        if isinstance(has_ticket_id_raw, list):
            has_ticket_id_raw = has_ticket_id_raw[0] if has_ticket_id_raw else ''
        
        # Nettoyer la valeur
        has_ticket_id = str(has_ticket_id_raw).strip() if has_ticket_id_raw else ''
        
        # FORCER les valeurs dans cleaned_data
        if has_ticket_id:
            cleaned_data['has_ticket_id'] = has_ticket_id
            # Supprimer l'erreur si elle existe
            if 'has_ticket_id' in self.errors:
                del self.errors['has_ticket_id']
        elif not has_ticket_id:
            # Si vide, ajouter l'erreur
            self.add_error('has_ticket_id', "Ce champ ne peut pas être vide.")
        
        return cleaned_data

    def save(self, commit=True):
        if 'ticket_type' not in self.cleaned_data:
            raise ValidationError("Le type de ticket est requis.")
        
        ticket_type = self.cleaned_data.pop('ticket_type')
        
        # Récupérer les champs communs
        has_ticket_id = self.cleaned_data.get('has_ticket_id') or self.data.get('has_ticket_id', '').strip()
        
        if not has_ticket_id:
            raise ValidationError("L'ID du ticket est requis.")
        
        common_data = {
            'has_ticket_id': has_ticket_id,
            'has_price': self.cleaned_data.pop('has_price', None),
            'has_validity_duration': self.cleaned_data.pop('has_validity_duration', None),
            'has_purchase_date': self.cleaned_data.pop('has_purchase_date', None),
            'has_expiration_date': self.cleaned_data.pop('has_expiration_date', None),
            'is_reduced_fare': self.cleaned_data.pop('is_reduced_fare', False),
            'owned_by': self.cleaned_data.pop('owned_by', None),
            'valid_for': self.cleaned_data.pop('valid_for', None),
        }

        model_map = {
            'ticketsimple': TicketSimple,
            'ticketsenior': TicketSenior,
            'ticketétudiant': TicketÉtudiant,
            'abonnementhebdomadaire': AbonnementHebdomadaire,
            'abonnementmensuel': AbonnementMensuel,
        }
        model = model_map[ticket_type]

        # Préparer les données spécifiques
        if ticket_type == 'ticketsimple':
            specific_data = {
                'is_used': self.cleaned_data.pop('is_used', False),
            }
        elif ticket_type == 'ticketsenior':
            specific_data = {
                'has_age_condition': self.cleaned_data.pop('has_age_condition', None),
            }
        elif ticket_type == 'ticketétudiant':
            specific_data = {
                'has_institution_name': self.cleaned_data.pop('has_institution_name', None),
                'has_student_id': self.cleaned_data.pop('has_student_id', None),
            }
        elif ticket_type == 'abonnementhebdomadaire':
            specific_data = {
                'has_start_date': self.cleaned_data.pop('has_start_date', None),
                'has_end_date': self.cleaned_data.pop('has_end_date', None),
                'has_zone_access': self.cleaned_data.pop('has_zone_access', None),
            }
        else:  # abonnementmensuel
            specific_data = {
                'has_month': self.cleaned_data.pop('has_month', None),
                'has_auto_renewal': self.cleaned_data.pop('has_auto_renewal', False),
                'has_payment_method': self.cleaned_data.pop('has_payment_method', None),
            }

        # Combiner toutes les données
        all_data = {**common_data, **specific_data}

        # Si on modifie une instance existante
        if self.instance and self.instance.pk:
            # Vérifier si on change de type
            current_type = None
            if isinstance(self.instance, TicketSimple):
                current_type = 'ticketsimple'
            elif isinstance(self.instance, TicketSenior):
                current_type = 'ticketsenior'
            elif isinstance(self.instance, TicketÉtudiant):
                current_type = 'ticketétudiant'
            elif isinstance(self.instance, AbonnementHebdomadaire):
                current_type = 'abonnementhebdomadaire'
            elif isinstance(self.instance, AbonnementMensuel):
                current_type = 'abonnementmensuel'

            # Si le type change, on doit créer une nouvelle instance
            if current_type != ticket_type:
                self.instance.delete()
                instance = model(**all_data)
            else:
                instance = self.instance
                for attr, value in all_data.items():
                    setattr(instance, attr, value)
        else:
            instance = model(**all_data)

        if commit:
            instance.full_clean()
            instance.save()

        return instance

