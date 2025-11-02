from django import forms
from .models import BusinessTrip, LeisureTrip, EducationalTrip
from .utils.ontology_manager import get_itinerary

class BusinessTripForm(forms.ModelForm):
    class Meta:
        model = BusinessTrip
        fields = [
            'itinerary_id', 
            'overall_status', 
            'total_cost_estimate', 
            'total_duration_days',
            'client_project_name', 
            'expense_limit', 
            'purpose_code', 
            'approval_required'
        ]
        widgets = {
            'itinerary_id': forms.TextInput(attrs={
                'placeholder': 'Enter base ID (e.g., 007)',
                'class': 'form-control'
            }),
            'overall_status': forms.Select(
                choices=[
                    ('Planned', 'Planned'),
                    ('InProgress', 'In Progress'),
                    ('Completed', 'Completed'),
                    ('Cancelled', 'Cancelled')
                ],
                attrs={'class': 'form-control'}
            ),
            'approval_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'total_cost_estimate': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': '0.00',
                'class': 'form-control'
            }),
            'total_duration_days': forms.NumberInput(attrs={
                'min': '1',
                'placeholder': '1',
                'class': 'form-control'
            }),
            'expense_limit': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': '0.00',
                'class': 'form-control'
            }),
            'client_project_name': forms.TextInput(attrs={
                'placeholder': 'Project name',
                'class': 'form-control'
            }),
            'purpose_code': forms.TextInput(attrs={
                'placeholder': 'e.g., MKT-PR',
                'class': 'form-control'
            }),
        }
        labels = {
            'itinerary_id': 'Itinerary ID (Base)',
            'overall_status': 'Status',
            'total_cost_estimate': 'Total Cost Estimate (TND)',
            'total_duration_days': 'Duration (Days)',
            'client_project_name': 'Project Name',
            'expense_limit': 'Expense Limit (TND)',
            'purpose_code': 'Purpose Code',
            'approval_required': 'Requires Approval',
        }
        help_texts = {
            'itinerary_id': 'Enter a unique ID (numbers/letters). Will be prefixed with "I-B-"',
        }
    
    def __init__(self, *args, **kwargs):
        # Store the original ID for update operations
        self.original_id = kwargs.pop('original_id', None)
        super().__init__(*args, **kwargs)
    
    def clean_itinerary_id(self):
        """Validate itinerary_id doesn't already exist in RDF (unless updating)"""
        itinerary_id = self.cleaned_data.get('itinerary_id')
        if not itinerary_id:
            raise forms.ValidationError('Itinerary ID is required.')
        
        # Remove any prefix if user added it
        itinerary_id = str(itinerary_id).replace('I-B-', '').replace('I-L-', '').replace('I-E-', '').strip()
        
        # Build full ID for checking
        full_id = f"I-B-{int(itinerary_id):03d}"
        
        # If updating, allow same ID
        if self.original_id:
            # Normalize original ID for comparison
            if self.original_id.startswith('I-B-'):
                original_normalized = self.original_id
            else:
                original_normalized = f"I-B-{int(self.original_id):03d}"
            
            if full_id == original_normalized:
                return itinerary_id
        
        # Check if ID exists in RDF store
        existing = get_itinerary(full_id)
        if existing:
            raise forms.ValidationError(f'Business trip with ID {full_id} already exists in RDF store.')
        
        return itinerary_id


class LeisureTripForm(forms.ModelForm):
    class Meta:
        model = LeisureTrip
        fields = [
            'itinerary_id', 
            'overall_status', 
            'total_cost_estimate', 
            'total_duration_days',
            'activity_type', 
            'accommodation', 
            'budget_per_day', 
            'group_size'
        ]
        widgets = {
            'itinerary_id': forms.TextInput(attrs={
                'placeholder': 'Enter base ID (e.g., 008)',
                'class': 'form-control'
            }),
            'overall_status': forms.Select(
                choices=[
                    ('Planned', 'Planned'),
                    ('InProgress', 'In Progress'),
                    ('Completed', 'Completed'),
                    ('Cancelled', 'Cancelled')
                ],
                attrs={'class': 'form-control'}
            ),
            'total_cost_estimate': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': '0.00',
                'class': 'form-control'
            }),
            'total_duration_days': forms.NumberInput(attrs={
                'min': '1',
                'placeholder': '1',
                'class': 'form-control'
            }),
            'budget_per_day': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': '0.00',
                'class': 'form-control'
            }),
            'group_size': forms.NumberInput(attrs={
                'min': '1',
                'placeholder': '1',
                'class': 'form-control'
            }),
            'activity_type': forms.TextInput(attrs={
                'placeholder': 'e.g., Adventure, Culture, Relaxation',
                'class': 'form-control'
            }),
            'accommodation': forms.TextInput(attrs={
                'placeholder': 'e.g., Hotel, Resort, Hostel',
                'class': 'form-control'
            }),
        }
        labels = {
            'itinerary_id': 'Itinerary ID (Base)',
            'overall_status': 'Status',
            'total_cost_estimate': 'Total Cost Estimate (TND)',
            'total_duration_days': 'Duration (Days)',
            'activity_type': 'Activity Type',
            'accommodation': 'Accommodation',
            'budget_per_day': 'Budget Per Day (TND)',
            'group_size': 'Group Size',
        }
        help_texts = {
            'itinerary_id': 'Enter a unique ID (numbers/letters). Will be prefixed with "I-L-"',
        }
    
    def __init__(self, *args, **kwargs):
        self.original_id = kwargs.pop('original_id', None)
        super().__init__(*args, **kwargs)
    
    def clean_itinerary_id(self):
        """Validate itinerary_id doesn't already exist in RDF (unless updating)"""
        itinerary_id = self.cleaned_data.get('itinerary_id')
        if not itinerary_id:
            raise forms.ValidationError('Itinerary ID is required.')
        
        itinerary_id = str(itinerary_id).replace('I-B-', '').replace('I-L-', '').replace('I-E-', '').strip()
        full_id = f"I-L-{int(itinerary_id):03d}"
        
        if self.original_id:
            original_normalized = self.original_id if self.original_id.startswith('I-L-') else f"I-L-{int(self.original_id):03d}"
            if full_id == original_normalized:
                return itinerary_id
        
        existing = get_itinerary(full_id)
        if existing:
            raise forms.ValidationError(f'Leisure trip with ID {full_id} already exists in RDF store.')
        
        return itinerary_id


class EducationalTripForm(forms.ModelForm):
    class Meta:
        model = EducationalTrip
        fields = [
            'itinerary_id', 
            'overall_status', 
            'total_cost_estimate', 
            'total_duration_days',
            'institution', 
            'course_reference', 
            'credit_hours', 
            'required_documentation'
        ]
        widgets = {
            'itinerary_id': forms.TextInput(attrs={
                'placeholder': 'Enter base ID (e.g., 009)',
                'class': 'form-control'
            }),
            'overall_status': forms.Select(
                choices=[
                    ('Planned', 'Planned'),
                    ('InProgress', 'In Progress'),
                    ('Completed', 'Completed'),
                    ('Cancelled', 'Cancelled')
                ],
                attrs={'class': 'form-control'}
            ),
            'total_cost_estimate': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': '0.00',
                'class': 'form-control'
            }),
            'total_duration_days': forms.NumberInput(attrs={
                'min': '1',
                'placeholder': '1',
                'class': 'form-control'
            }),
            'credit_hours': forms.NumberInput(attrs={
                'min': '0',
                'placeholder': '0',
                'class': 'form-control'
            }),
            'institution': forms.TextInput(attrs={
                'placeholder': 'e.g., City University',
                'class': 'form-control'
            }),
            'course_reference': forms.TextInput(attrs={
                'placeholder': 'e.g., HIS-301',
                'class': 'form-control'
            }),
            'required_documentation': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'e.g., Passport, Acceptance Letter',
                'class': 'form-control'
            }),
        }
        labels = {
            'itinerary_id': 'Itinerary ID (Base)',
            'overall_status': 'Status',
            'total_cost_estimate': 'Total Cost Estimate (TND)',
            'total_duration_days': 'Duration (Days)',
            'institution': 'Institution',
            'course_reference': 'Course Reference',
            'credit_hours': 'Credit Hours',
            'required_documentation': 'Required Documentation',
        }
        help_texts = {
            'itinerary_id': 'Enter a unique ID (numbers/letters). Will be prefixed with "I-E-"',
        }
    
    def __init__(self, *args, **kwargs):
        self.original_id = kwargs.pop('original_id', None)
        super().__init__(*args, **kwargs)
    
    def clean_itinerary_id(self):
        """Validate itinerary_id doesn't already exist in RDF (unless updating)"""
        itinerary_id = self.cleaned_data.get('itinerary_id')
        if not itinerary_id:
            raise forms.ValidationError('Itinerary ID is required.')
        
        itinerary_id = str(itinerary_id).replace('I-B-', '').replace('I-L-', '').replace('I-E-', '').strip()
        full_id = f"I-E-{int(itinerary_id):03d}"
        
        if self.original_id:
            original_normalized = self.original_id if self.original_id.startswith('I-E-') else f"I-E-{int(self.original_id):03d}"
            if full_id == original_normalized:
                return itinerary_id
        
        existing = get_itinerary(full_id)
        if existing:
            raise forms.ValidationError(f'Educational trip with ID {full_id} already exists in RDF store.')
        
        return itinerary_id