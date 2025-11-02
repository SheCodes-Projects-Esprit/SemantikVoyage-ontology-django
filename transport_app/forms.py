# transport_app/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    BusStop, MetroStation, TrainStation, TramStation,
    Bus, Metro, Train, Tram, City, Schedule,
    BusCompany, MetroCompany,
    Station, Company, Person, Conducteur, Contrôleur, EmployéAgence, Passager
)


class StationForm(forms.ModelForm):
    station_type = forms.ChoiceField(
        choices=[
            ('busstop', 'Arrêt de Bus'),
            ('metrostation', 'Station de Métro'),
            ('trainstation', 'Gare'),
            ('tramstation', 'Arrêt de Tram'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = BusStop
        fields = ['station_type', 'station_name', 'station_location', 'station_accessibility', 'located_in']
        widgets = {
            'station_name': forms.TextInput(attrs={'placeholder': 'Bab El Khadhra'}),
            'station_location': forms.TextInput(attrs={'placeholder': 'Rue de Rome'}),
            'located_in': forms.Select(attrs={'class': 'form-select'}),
        }

    def save(self, commit=True):
        station_type = self.cleaned_data.pop('station_type')
        model_map = {
            'busstop': BusStop,
            'metrostation': MetroStation,
            'trainstation': TrainStation,
            'tramstation': TramStation,
        }
        model = model_map[station_type]
        instance = model(**self.cleaned_data)
        if commit:
            instance.full_clean()
            instance.save()
        return instance


class TransportForm(forms.ModelForm):
    transport_type = forms.ChoiceField(
        choices=[
            ('bus', 'Bus'),
            ('metro', 'Métro'),
            ('train', 'Train'),
            ('tram', 'Tram'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    departs_from = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    arrives_at = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    operated_by = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )

    class Meta:
        model = Bus
        fields = [
            'transport_type', 'transport_line_number', 'transport_capacity',
            'transport_speed', 'transport_frequency', 'operates_in', 'applies_to'
        ]
        widgets = {
            'operates_in': forms.CheckboxSelectMultiple(),
            'applies_to': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # === STATIONS ===
        station_choices = [('', '— Choisir une station —')]
        for model in [BusStop, MetroStation, TrainStation, TramStation]:
            for obj in model.objects.all():
                station_choices.append((str(obj.pk), f"{obj.get_type()} — {obj.station_name}"))
        station_choices.sort(key=lambda x: x[1])
        self.fields['departs_from'].choices = station_choices
        self.fields['arrives_at'].choices = station_choices

        # === COMPAGNIES ===
        company_choices = [('', '— Choisir une compagnie —')]
        for model in [BusCompany, MetroCompany]:
            for obj in model.objects.all():
                company_choices.append((str(obj.pk), f"{obj.get_type()} — {obj.company_name}"))
        company_choices.sort(key=lambda x: x[1])
        self.fields['operated_by'].choices = company_choices

        # Pré-remplissage
        if self.instance and self.instance.pk:
            if self.instance.departs_from:
                self.fields['departs_from'].initial = str(self.instance.departs_from.pk)
            if self.instance.arrives_at:
                self.fields['arrives_at'].initial = str(self.instance.arrives_at.pk)
            if self.instance.operated_by:
                self.fields['operated_by'].initial = str(self.instance.operated_by.pk)

    def clean_departs_from(self):
        value = self.cleaned_data.get('departs_from')
        if not value:
            return None
        try:
            pk = int(value)
            return Station.get_subclass(pk)
        except (ValueError, Station.DoesNotExist):
            raise ValidationError("Station de départ invalide.")

    def clean_arrives_at(self):
        value = self.cleaned_data.get('arrives_at')
        if not value:
            return None
        try:
            pk = int(value)
            return Station.get_subclass(pk)
        except (ValueError, Station.DoesNotExist):
            raise ValidationError("Station d'arrivée invalide.")

    def clean_operated_by(self):
        value = self.cleaned_data.get('operated_by')
        if not value:
            return None
        try:
            pk = int(value)
            return Company.get_subclass(pk)
        except (ValueError, Company.DoesNotExist):
            raise ValidationError("Compagnie invalide.")

    def save(self, commit=True):
        ttype = self.cleaned_data.pop('transport_type')
        model_map = {'bus': Bus, 'metro': Metro, 'train': Train, 'tram': Tram}
        model = model_map[ttype]

        operates_in = self.cleaned_data.pop('operates_in', None)

        # Ici : on récupère directement les objets nettoyés
        departs_from = self.cleaned_data.pop('departs_from', None)
        arrives_at = self.cleaned_data.pop('arrives_at', None)
        operated_by = self.cleaned_data.pop('operated_by', None)

        # Création / mise à jour
        if self.instance and self.instance.pk:
            instance = self.instance
            for attr, value in self.cleaned_data.items():
                setattr(instance, attr, value)
        else:
            instance = model(**self.cleaned_data)

        instance.departs_from = departs_from
        instance.arrives_at = arrives_at
        instance.operated_by = operated_by

        if commit:
            try:
                instance.full_clean()
                instance.save()
                if operates_in is not None:
                    instance.operates_in.set(operates_in)
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            self.add_error(field, error)
                else:
                    self.add_error(None, str(e))
                raise

        return instance


# === PERSON FORMS ===
class PersonForm(forms.ModelForm):
    person_type = forms.ChoiceField(
        choices=[
            ('conducteur', 'Conducteur'),
            ('controleur', 'Contrôleur'),
            ('employeagence', 'Employé Agence'),
            ('passager', 'Passager'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'person_type'}),
        label="Type de personne"
    )

    # Champs communs à toutes les Personnes
    # NOTE: required=False pour que Django appelle toujours clean_FIELD()
    # La validation obligatoire est gérée dans clean_has_id() et clean_has_name()
    has_id = forms.CharField(
        max_length=50,
        required=False,  # Gérer la validation dans clean_has_id()
        widget=forms.TextInput(attrs={'placeholder': 'P-001, C-001, etc.', 'class': 'form-control'}),
        label="ID",
        help_text="Identifiant unique de la personne (obligatoire)",
        strip=True  # Strip automatiquement les espaces
    )
    has_name = forms.CharField(
        max_length=255,
        required=False,  # Gérer la validation dans clean_has_name()
        widget=forms.TextInput(attrs={'placeholder': 'Nom complet', 'class': 'form-control'}),
        label="Nom",
        help_text="Nom complet de la personne (obligatoire)",
        strip=True  # Strip automatiquement les espaces
    )
    has_age = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Âge"
    )
    has_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'email@example.com', 'class': 'form-control'}),
        label="Email"
    )
    has_phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+21650123456', 'class': 'form-control'}),
        label="Téléphone"
    )
    has_role = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Rôle', 'class': 'form-control'}),
        label="Rôle"
    )

    # Champs spécifiques Conducteur
    has_license_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_conducteur_license'}),
        label="Numéro de permis"
    )
    has_experience_years = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'field_conducteur_experience'}),
        label="Années d'expérience"
    )
    drives_line = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_conducteur_line'}),
        label="Ligne conduite"
    )
    has_work_shift = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_conducteur_shift'}),
        label="Tranche horaire"
    )
    works_for = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'field_conducteur_company'}),
        required=False,
        label="Travaille pour (Compagnie)"
    )

    # Champs spécifiques Contrôleur
    has_badge_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_controleur_badge'}),
        label="Numéro de badge"
    )
    has_assigned_zone = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_controleur_zone'}),
        label="Zone assignée"
    )
    has_inspection_count = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'field_controleur_inspections'}),
        label="Nombre d'inspections"
    )
    works_for_company = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_controleur_company'}),
        label="Nom de la compagnie"
    )

    # Champs spécifiques EmployéAgence
    has_employee_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_employeagence_employeeid'}),
        label="Numéro d'employé"
    )
    has_position = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_employeagence_position'}),
        label="Poste"
    )
    works_at = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_employeagence_worksat'}),
        label="Lieu de travail"
    )
    has_schedule = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'field_employeagence_schedule'}),
        required=False,
        label="Horaires"
    )

    # Champs spécifiques Passager
    has_subscription_type = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_passager_subscription'}),
        label="Type d'abonnement"
    )
    has_preferred_transport = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'field_passager_transport'}),
        label="Transport préféré"
    )

    class Meta:
        model = Person
        fields = []  # Tous les champs sont définis manuellement
    
    def full_clean(self):
        """Override full_clean pour forcer les valeurs et supprimer les erreurs"""
        # Appeler super().full_clean() qui appelle _clean_fields(), clean(), et _post_clean()
        super().full_clean()
        
        # S'assurer que cleaned_data existe (peut ne pas exister pour les requêtes GET)
        if not hasattr(self, 'cleaned_data'):
            self.cleaned_data = {}
        
        # APRÈS full_clean(), forcer les valeurs et supprimer les erreurs
        has_id_raw = self.data.get('has_id', '')
        has_name_raw = self.data.get('has_name', '')
        
        # Gérer le cas QueryDict (liste)
        if isinstance(has_id_raw, list):
            has_id_raw = has_id_raw[0] if has_id_raw else ''
        if isinstance(has_name_raw, list):
            has_name_raw = has_name_raw[0] if has_name_raw else ''
        
        # Nettoyer les valeurs
        has_id = str(has_id_raw).strip() if has_id_raw else ''
        has_name = str(has_name_raw).strip() if has_name_raw else ''
        
        print(f"[DEBUG] full_clean() AFTER super() - forcing values - has_id: {repr(has_id)}, has_name: {repr(has_name)}")
        
        # FORCER les valeurs dans cleaned_data
        if has_id:
            self.cleaned_data['has_id'] = has_id
            # Supprimer l'erreur si elle existe
            if 'has_id' in self.errors:
                del self.errors['has_id']
                print(f"[DEBUG] full_clean() removed has_id error")
        elif not has_id and self.data:  # Seulement si c'est une soumission de formulaire
            # Ne pas ajouter d'erreur pour les requêtes GET
            if 'has_id' not in self.cleaned_data:
                self.cleaned_data['has_id'] = ''
        
        if has_name:
            self.cleaned_data['has_name'] = has_name
            # Supprimer l'erreur si elle existe
            if 'has_name' in self.errors:
                del self.errors['has_name']
                print(f"[DEBUG] full_clean() removed has_name error")
        elif not has_name and self.data:  # Seulement si c'est une soumission de formulaire
            # Ne pas ajouter d'erreur pour les requêtes GET
            if 'has_name' not in self.cleaned_data:
                self.cleaned_data['has_name'] = ''
        
        print(f"[DEBUG] full_clean() FINAL - has_id in cleaned_data: {'has_id' in self.cleaned_data}, value: {repr(self.cleaned_data.get('has_id'))}")
        print(f"[DEBUG] full_clean() FINAL - has_name in cleaned_data: {'has_name' in self.cleaned_data}, value: {repr(self.cleaned_data.get('has_name'))}")
        print(f"[DEBUG] full_clean() FINAL - errors: {list(self.errors.keys())}")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # === COMPAGNIES ===
        company_choices = [('', '— Choisir une compagnie —')]
        for model in [BusCompany, MetroCompany]:
            for obj in model.objects.all():
                company_choices.append((str(obj.pk), f"{obj.__class__.__name__} — {obj.company_name}"))
        company_choices.sort(key=lambda x: x[1])
        self.fields['works_for'].choices = company_choices

        # === SCHEDULES ===
        schedule_choices = [('', '— Choisir un horaire —')]
        for schedule in Schedule.objects.all():
            schedule_choices.append((str(schedule.pk), f"{schedule.schedule_id} - {schedule.route_name or 'No Route'}"))
        self.fields['has_schedule'].choices = schedule_choices

        # Si on modifie une instance existante
        if self.instance and self.instance.pk:
            # Remplir les champs communs
            self.fields['has_id'].initial = self.instance.has_id
            self.fields['has_name'].initial = self.instance.has_name
            self.fields['has_age'].initial = self.instance.has_age
            self.fields['has_email'].initial = self.instance.has_email
            self.fields['has_phone_number'].initial = self.instance.has_phone_number
            self.fields['has_role'].initial = self.instance.has_role

            # Déterminer le type et remplir les champs spécifiques
            if isinstance(self.instance, Conducteur):
                self.fields['person_type'].initial = 'conducteur'
                self.fields['has_license_number'].initial = self.instance.has_license_number
                self.fields['has_experience_years'].initial = self.instance.has_experience_years
                self.fields['drives_line'].initial = self.instance.drives_line
                self.fields['has_work_shift'].initial = self.instance.has_work_shift
                if self.instance.works_for:
                    self.fields['works_for'].initial = str(self.instance.works_for.pk)
            elif isinstance(self.instance, Contrôleur):
                self.fields['person_type'].initial = 'controleur'
                self.fields['has_badge_id'].initial = self.instance.has_badge_id
                self.fields['has_assigned_zone'].initial = self.instance.has_assigned_zone
                self.fields['has_inspection_count'].initial = self.instance.has_inspection_count
                self.fields['works_for_company'].initial = self.instance.works_for_company
            elif isinstance(self.instance, EmployéAgence):
                self.fields['person_type'].initial = 'employeagence'
                self.fields['has_employee_id'].initial = self.instance.has_employee_id
                self.fields['has_position'].initial = self.instance.has_position
                self.fields['works_at'].initial = self.instance.works_at
                if self.instance.has_schedule:
                    self.fields['has_schedule'].initial = str(self.instance.has_schedule.pk)
            elif isinstance(self.instance, Passager):
                self.fields['person_type'].initial = 'passager'
                self.fields['has_subscription_type'].initial = self.instance.has_subscription_type
                self.fields['has_preferred_transport'].initial = self.instance.has_preferred_transport

    def clean_works_for(self):
        """Valider et récupérer l'objet Company"""
        value = self.cleaned_data.get('works_for')
        if not value:
            return None
        try:
            pk = int(value)
            return Company.get_subclass(pk)
        except (ValueError, Company.DoesNotExist):
            raise ValidationError("Compagnie invalide.")

    def clean_has_schedule(self):
        """Valider et récupérer l'objet Schedule"""
        value = self.cleaned_data.get('has_schedule')
        if not value:
            return None
        try:
            pk = int(value)
            return Schedule.objects.get(pk=pk)
        except (ValueError, Schedule.DoesNotExist):
            raise ValidationError("Horaire invalide.")

    def clean_has_id(self):
        """Valider et nettoyer has_id - TOUJOURS récupérer depuis self.data"""
        # TOUJOURS récupérer depuis self.data (données POST brutes)
        value = self.data.get('has_id', '')
        
        # Gérer le cas QueryDict (liste)
        if isinstance(value, list):
            value = value[0] if value else ''
        
        # Nettoyer la valeur
        if value:
            value = str(value).strip()
        else:
            value = ''
        
        print(f"[DEBUG] clean_has_id() CALLED, value from data: {repr(self.data.get('has_id'))}, final: {repr(value)}")
        
        if not value:
            raise ValidationError("Ce champ ne peut pas être vide.")
        
        return value
    
    def clean_has_name(self):
        """Valider et nettoyer has_name - TOUJOURS récupérer depuis self.data"""
        # TOUJOURS récupérer depuis self.data (données POST brutes)
        value = self.data.get('has_name', '')
        
        # Gérer le cas QueryDict (liste)
        if isinstance(value, list):
            value = value[0] if value else ''
        
        # Nettoyer la valeur
        if value:
            value = str(value).strip()
        else:
            value = ''
        
        print(f"[DEBUG] clean_has_name() CALLED, value from data: {repr(self.data.get('has_name'))}, final: {repr(value)}")
        
        if not value:
            raise ValidationError("Ce champ ne peut pas être vide.")
        
        return value
    
    def clean(self):
        """Validation globale du formulaire"""
        cleaned_data = super().clean()
        
        # Debug final
        print(f"[DEBUG] clean() called, cleaned_data keys: {list(cleaned_data.keys())}")
        print(f"[DEBUG] has_id in cleaned_data: {'has_id' in cleaned_data}, value: {repr(cleaned_data.get('has_id'))}")
        print(f"[DEBUG] has_name in cleaned_data: {'has_name' in cleaned_data}, value: {repr(cleaned_data.get('has_name'))}")
        
        # FORCER les valeurs dans cleaned_data et supprimer les erreurs
        # Récupérer depuis self.data (toujours disponible)
        has_id_raw = self.data.get('has_id', '')
        has_name_raw = self.data.get('has_name', '')
        
        # Gérer le cas QueryDict (liste)
        if isinstance(has_id_raw, list):
            has_id_raw = has_id_raw[0] if has_id_raw else ''
        if isinstance(has_name_raw, list):
            has_name_raw = has_name_raw[0] if has_name_raw else ''
        
        # Nettoyer les valeurs
        has_id = str(has_id_raw).strip() if has_id_raw else ''
        has_name = str(has_name_raw).strip() if has_name_raw else ''
        
        print(f"[DEBUG] clean() forcing values - has_id: {repr(has_id)}, has_name: {repr(has_name)}")
        
        # FORCER les valeurs dans cleaned_data
        if has_id:
            cleaned_data['has_id'] = has_id
            # Supprimer l'erreur si elle existe
            if 'has_id' in self.errors:
                del self.errors['has_id']
                print(f"[DEBUG] clean() removed has_id error")
        elif not has_id:
            # Si vide, ajouter l'erreur
            self.add_error('has_id', "Ce champ ne peut pas être vide.")
        
        if has_name:
            cleaned_data['has_name'] = has_name
            # Supprimer l'erreur si elle existe
            if 'has_name' in self.errors:
                del self.errors['has_name']
                print(f"[DEBUG] clean() removed has_name error")
        elif not has_name:
            # Si vide, ajouter l'erreur
            self.add_error('has_name', "Ce champ ne peut pas être vide.")
        
        print(f"[DEBUG] clean() FINAL - has_id in cleaned_data: {'has_id' in cleaned_data}, value: {repr(cleaned_data.get('has_id'))}")
        print(f"[DEBUG] clean() FINAL - has_name in cleaned_data: {'has_name' in cleaned_data}, value: {repr(cleaned_data.get('has_name'))}")
        print(f"[DEBUG] clean() FINAL - errors: {list(self.errors.keys())}")
        
        return cleaned_data
    
    def save(self, commit=True):
        if 'person_type' not in self.cleaned_data:
            raise ValidationError("Le type de personne est requis.")
        
        person_type = self.cleaned_data.pop('person_type')
        
        # Récupérer les champs communs - récupérer depuis cleaned_data ou depuis data si nécessaire
        has_id = self.cleaned_data.get('has_id') or self.data.get('has_id', '').strip()
        has_name = self.cleaned_data.get('has_name') or self.data.get('has_name', '').strip()
        
        # Nettoyer les valeurs
        if has_id:
            has_id = str(has_id).strip()
        else:
            has_id = ''
            
        if has_name:
            has_name = str(has_name).strip()
        else:
            has_name = ''
        
        # Pop depuis cleaned_data si présents
        self.cleaned_data.pop('has_id', None)
        self.cleaned_data.pop('has_name', None)
        
        if not has_id:
            raise ValidationError("L'ID est requis.")
        if not has_name:
            raise ValidationError("Le nom est requis.")
        
        common_data = {
            'has_id': has_id,
            'has_name': has_name,
            'has_age': self.cleaned_data.pop('has_age', None),
            'has_email': self.cleaned_data.pop('has_email', None),
            'has_phone_number': self.cleaned_data.pop('has_phone_number', None),
            'has_role': self.cleaned_data.pop('has_role', None),
        }

        model_map = {
            'conducteur': Conducteur,
            'controleur': Contrôleur,
            'employeagence': EmployéAgence,
            'passager': Passager,
        }
        model = model_map[person_type]

        # Préparer les données spécifiques
        if person_type == 'conducteur':
            specific_data = {
                'has_license_number': self.cleaned_data.pop('has_license_number', None),
                'has_experience_years': self.cleaned_data.pop('has_experience_years', None),
                'drives_line': self.cleaned_data.pop('drives_line', None),
                'has_work_shift': self.cleaned_data.pop('has_work_shift', None),
                'works_for': self.cleaned_data.pop('works_for', None),
            }
        elif person_type == 'controleur':
            specific_data = {
                'has_badge_id': self.cleaned_data.pop('has_badge_id', None),
                'has_assigned_zone': self.cleaned_data.pop('has_assigned_zone', None),
                'has_inspection_count': self.cleaned_data.pop('has_inspection_count', None),
                'works_for_company': self.cleaned_data.pop('works_for_company', None),
            }
        elif person_type == 'employeagence':
            specific_data = {
                'has_employee_id': self.cleaned_data.pop('has_employee_id', None),
                'has_position': self.cleaned_data.pop('has_position', None),
                'works_at': self.cleaned_data.pop('works_at', None),
                'has_schedule': self.cleaned_data.pop('has_schedule', None),
            }
        else:  # passager
            specific_data = {
                'has_subscription_type': self.cleaned_data.pop('has_subscription_type', None),
                'has_preferred_transport': self.cleaned_data.pop('has_preferred_transport', None),
            }

        # Combiner toutes les données
        all_data = {**common_data, **specific_data}

        # Si on modifie une instance existante
        if self.instance and self.instance.pk:
            # Vérifier si on change de type
            current_type = None
            if isinstance(self.instance, Conducteur):
                current_type = 'conducteur'
            elif isinstance(self.instance, Contrôleur):
                current_type = 'controleur'
            elif isinstance(self.instance, EmployéAgence):
                current_type = 'employeagence'
            elif isinstance(self.instance, Passager):
                current_type = 'passager'

            # Si le type change, on doit créer une nouvelle instance
            if current_type != person_type:
                # Supprimer l'ancienne instance
                self.instance.delete()
                # Créer une nouvelle instance du nouveau type
                instance = model(**all_data)
            else:
                # Même type, on met juste à jour
                instance = self.instance
                for attr, value in all_data.items():
                    setattr(instance, attr, value)
        else:
            # Nouvelle instance
            instance = model(**all_data)

        if commit:
            instance.full_clean()
            instance.save()

        return instance