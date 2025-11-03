from django import forms
from .models import Company
from .utils.ontology_manager import get_company


class CompanyForm(forms.ModelForm):
    name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. OpenAI',
            'class': 'form-control'
        }),
        label='Company Name',
        help_text='Enter the official company name'
    )

    def __init__(self, *args, **kwargs):
        self.original_name = kwargs.pop('original_name', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('Company name is required.')
        if self.original_name and self.original_name.strip().lower() == name.lower():
            return name
        if get_company(name):
            raise forms.ValidationError(f"Company '{name}' already exists in RDF store.")
        return name

    class Meta:
        model = Company
        fields = ['name']


class BusCompanyForm(CompanyForm):
    number_of_employees = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Employees')
    founded_year = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1963'}), label='Founded Year')
    headquarters_location = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Tunis'}), label='Headquarters')
    number_of_bus_lines = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Bus Lines')
    average_bus_age = forms.FloatField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}), label='Average Bus Age')
    ticket_price = forms.FloatField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}), label='Ticket Price')
    eco_friendly_fleet = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), label='Eco-friendly Fleet')

    class Meta(CompanyForm.Meta):
        fields = ['name', 'number_of_employees', 'founded_year', 'headquarters_location', 'number_of_bus_lines', 'average_bus_age', 'ticket_price', 'eco_friendly_fleet']


class MetroCompanyForm(CompanyForm):
    number_of_employees = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Employees')
    founded_year = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Founded Year')
    headquarters_location = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Headquarters')
    number_of_lines = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Lines')
    total_track_length = forms.FloatField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}), label='Track Length (km)')
    automation_level = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Automation Level')
    daily_passengers = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Daily Passengers')

    class Meta(CompanyForm.Meta):
        fields = ['name', 'number_of_employees', 'founded_year', 'headquarters_location', 'number_of_lines', 'total_track_length', 'automation_level', 'daily_passengers']


class TaxiCompanyForm(CompanyForm):
    number_of_employees = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Employees')
    founded_year = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Founded Year')
    headquarters_location = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Headquarters')
    number_of_vehicles = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Vehicles')
    booking_app = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), label='Booking App')
    average_fare_per_km = forms.FloatField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}), label='Avg Fare / km')

    class Meta(CompanyForm.Meta):
        fields = ['name', 'number_of_employees', 'founded_year', 'headquarters_location', 'number_of_vehicles', 'booking_app', 'average_fare_per_km']


class BikeSharingCompanyForm(CompanyForm):
    number_of_employees = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Employees')
    founded_year = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Founded Year')
    headquarters_location = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Headquarters')
    number_of_stations = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Stations')
    bike_count = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Bikes')
    subscription_price = forms.FloatField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}), label='Subscription Price')
    electric_bikes = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), label='Electric Bikes')

    class Meta(CompanyForm.Meta):
        fields = ['name', 'number_of_employees', 'founded_year', 'headquarters_location', 'number_of_stations', 'bike_count', 'subscription_price', 'electric_bikes']

