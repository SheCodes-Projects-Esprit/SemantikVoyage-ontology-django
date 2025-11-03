from django import forms


class BaseScheduleForm(forms.Form):
    schedule_id = forms.CharField(
        label='Schedule ID (number or full ID)', max_length=32, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 12 or S-S-012'})
    )
    route_name = forms.CharField(
        label='Route Name', max_length=128, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Red Line Express'})
    )
    effective_date = forms.CharField(
        label='Effective Date', max_length=64, required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'})
    )
    is_public = forms.BooleanField(label='Is Public', required=False)


class ScheduleForm(BaseScheduleForm):
    pass


class DailyScheduleForm(BaseScheduleForm):
    first_run_time = forms.CharField(
        label='First Run Time', max_length=32, required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'placeholder': 'HH:MM'})
    )
    last_run_time = forms.CharField(
        label='Last Run Time', max_length=32, required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'placeholder': 'HH:MM'})
    )
    frequency_minutes = forms.IntegerField(
        label='Frequency Minutes', min_value=0, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 15'})
    )
    day_of_week_mask = forms.CharField(
        label='Day Of Week Mask', max_length=32, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Mon-Fri or 1111100'})
    )


class SeasonalScheduleForm(BaseScheduleForm):
    season = forms.CharField(
        label='Season', max_length=32, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Holiday'})
    )
    start_date = forms.CharField(
        label='Season Start Date', max_length=64, required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'})
    )
    end_date = forms.CharField(
        label='Season End Date', max_length=64, required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'})
    )
    operational_capacity_percentage = forms.IntegerField(
        label='Operational Capacity %', min_value=0, required=False,
        widget=forms.NumberInput(attrs={'placeholder': '0-100'})
    )


class OnDemandScheduleForm(BaseScheduleForm):
    booking_lead_time_hours = forms.IntegerField(
        label='Booking Lead Time Hours', min_value=0, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 2'})
    )
    service_window_start = forms.CharField(
        label='Service Window Start', max_length=32, required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'placeholder': 'HH:MM'})
    )
    service_window_end = forms.CharField(
        label='Service Window End', max_length=32, required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'placeholder': 'HH:MM'})
    )
    max_wait_time_minutes = forms.IntegerField(
        label='Max Wait Time Minutes', min_value=0, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 10'})
    )


