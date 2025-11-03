from django import forms
from .models import CapitalCity, MetropolitanCity, TouristicCity, IndustrialCity
from .utils.ontology_manager import get_city


class CityFormMixin:
    def __init__(self, *args, **kwargs):
        self.original_name = kwargs.pop('original_name', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        """Validate city name uniqueness against RDF (unless updating same name)."""
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('City name is required.')

        if self.original_name and str(self.original_name).strip().lower() == name.lower():
            return name

        if get_city(name):
            raise forms.ValidationError(f"City '{name}' already exists in RDF store.")

        return name


# =============================================================================
# CAPITAL CITY FORM
# =============================================================================
class CapitalCityForm(CityFormMixin, forms.ModelForm):
    # ADD NAME FIELD
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Tunis',
            'class': 'form-control'
        }),
        label='City Name',
        help_text='Enter the official city name'
    )

    class Meta:
        model = CapitalCity
        fields = [
            'name', 'population', 'area_km2',
            'government_seat', 'ministries'
        ]
        widgets = {
            'population': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 1050000',
                'class': 'form-control'
            }),
            'area_km2': forms.NumberInput(attrs={
                'step': '0.1',
                'min': 0,
                'placeholder': 'e.g. 212.6',
                'class': 'form-control'
            }),
            'government_seat': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ministries': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 20',
                'class': 'form-control'
            }),
        }
        labels = {
            'population': 'Population',
            'area_km2': 'Area (km²)',
            'government_seat': 'Government Seat',
            'ministries': 'Number of Ministries',
        }
        help_texts = {
            'area_km2': 'Total area in square kilometers.',
            'population': 'Current estimated population.',
        }


# =============================================================================
# METROPOLITAN CITY FORM
# =============================================================================
class MetropolitanCityForm(CityFormMixin, forms.ModelForm):
    # ADD NAME FIELD
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Sfax',
            'class': 'form-control'
        }),
        label='City Name',
        help_text='Enter the official city name'
    )

    class Meta:
        model = MetropolitanCity
        fields = [
            'name', 'population', 'area_km2',
            'districts', 'commute_minutes'
        ]
        widgets = {
            'population': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 955000',
                'class': 'form-control'
            }),
            'area_km2': forms.NumberInput(attrs={
                'step': '0.1',
                'min': 0,
                'placeholder': 'e.g. 220.0',
                'class': 'form-control'
            }),
            'districts': forms.NumberInput(attrs={
                'min': 1,
                'placeholder': 'e.g. 15',
                'class': 'form-control'
            }),
            'commute_minutes': forms.NumberInput(attrs={
                'step': '0.1',
                'min': 0,
                'placeholder': 'e.g. 35.0',
                'class': 'form-control'
            }),
        }
        labels = {
            'population': 'Population',
            'area_km2': 'Area (km²)',
            'districts': 'Number of Districts',
            'commute_minutes': 'Avg. Commute Time (min)',
        }
        help_texts = {
            'commute_minutes': 'Average daily commute time in minutes.',
        }


# =============================================================================
# TOURISTIC CITY FORM
# =============================================================================
class TouristicCityForm(CityFormMixin, forms.ModelForm):
    # ADD NAME FIELD
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Sousse',
            'class': 'form-control'
        }),
        label='City Name',
        help_text='Enter the official city name'
    )

    class Meta:
        model = TouristicCity
        fields = [
            'name', 'population', 'area_km2',
            'annual_visitors', 'hotels'
        ]
        widgets = {
            'population': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 221530',
                'class': 'form-control'
            }),
            'area_km2': forms.NumberInput(attrs={
                'step': '0.1',
                'min': 0,
                'placeholder': 'e.g. 45.0',
                'class': 'form-control'
            }),
            'annual_visitors': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 1500000',
                'class': 'form-control'
            }),
            'hotels': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 80',
                'class': 'form-control'
            }),
        }
        labels = {
            'population': 'Population',
            'area_km2': 'Area (km²)',
            'annual_visitors': 'Annual Visitors',
            'hotels': 'Number of Hotels',
        }
        help_texts = {
            'annual_visitors': 'Estimated yearly tourist arrivals.',
        }


# =============================================================================
# INDUSTRIAL CITY FORM
# =============================================================================
class IndustrialCityForm(CityFormMixin, forms.ModelForm):
    # ADD NAME FIELD
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. Bizerte',
            'class': 'form-control'
        }),
        label='City Name',
        help_text='Enter the official city name'
    )

    class Meta:
        model = IndustrialCity
        fields = [
            'name', 'population', 'area_km2',
            'factories', 'pollution_index'
        ]
        widgets = {
            'population': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 142966',
                'class': 'form-control'
            }),
            'area_km2': forms.NumberInput(attrs={
                'step': '0.1',
                'min': 0,
                'placeholder': 'e.g. 63.0',
                'class': 'form-control'
            }),
            'factories': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'e.g. 60',
                'class': 'form-control'
            }),
            'pollution_index': forms.NumberInput(attrs={
                'step': '0.1',
                'min': 0,
                'max': 100,
                'placeholder': 'e.g. 48.7',
                'class': 'form-control'
            }),
        }
        labels = {
            'population': 'Population',
            'area_km2': 'Area (km²)',
            'factories': 'Number of Factories',
            'pollution_index': 'Pollution Index (0–100)',
        }
        help_texts = {
            'pollution_index': 'Air quality index (lower = cleaner).',
        }