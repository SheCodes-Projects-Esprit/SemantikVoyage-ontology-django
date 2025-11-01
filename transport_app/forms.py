# transport_app/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    BusStop, MetroStation, TrainStation, TramStation,
    Bus, Metro, Train, Tram, City, Schedule,
    BusCompany, MetroCompany,
    Station, Company
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