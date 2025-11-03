from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from .forms import (
    ScheduleForm, DailyScheduleForm, SeasonalScheduleForm, OnDemandScheduleForm
)
from .utils.ontology_manager import (
    list_schedules, get_schedule, create_schedule, update_schedule, delete_schedule
)
from .utils.ai_nl_interface import ai_generate_and_execute


def schedule_list(request):
    filters = request.GET.dict()
    rows = list_schedules(filters)
    rows.sort(key=lambda x: x['id'])
    return render(request, 'core/schedule/schedule_list.html', {
        'schedules': rows,
        'filters': filters,
    })


def schedule_detail(request, id: str):
    subject_uri = request.GET.get('s')
    sched = get_schedule(id, subject_uri=subject_uri)
    if not sched:
        messages.error(request, f"Schedule {id} not found in RDF store.")
        return redirect('schedule:list')
    # Derive readable type
    tval = sched.get('type', '')
    if 'Daily' in tval:
        type_name = 'Daily'
        icon = '🗓️'
    elif 'Seasonal' in tval:
        type_name = 'Seasonal'
        icon = '🍂'
    elif 'OnDemand' in tval:
        type_name = 'OnDemand'
        icon = '📞'
    else:
        type_name = 'Schedule'
        icon = '⏱️'

    # Fields to display (skip empty)
    def v(key):
        return sched.get(key) or ''

    rows = [
        ('Schedule ID', v('scheduleID') or id),
        ('Type', type_name),
        ('Route', v('routeName')),
        ('Effective Date', v('effectiveDate')),
        ('Public', v('isPublic')),
        # Daily
        ('First Run Time', v('firstRunTime')),
        ('Last Run Time', v('lastRunTime')),
        ('Frequency Minutes', v('frequencyMinutes')),
        ('Day Of Week Mask', v('dayOfWeekMask')),
        # Seasonal
        ('Season', v('season')),
        ('Start Date', v('startDate')),
        ('End Date', v('endDate')),
        ('Operational Capacity %', v('operationalCapacityPercentage')),
        # OnDemand
        ('Booking Lead Time Hours', v('bookingLeadTimeHours')),
        ('Service Window Start', v('serviceWindowStart')),
        ('Service Window End', v('serviceWindowEnd')),
        ('Max Wait Time Minutes', v('maxWaitTimeMinutes')),
    ]
    rows = [r for r in rows if r[1]]

    return render(request, 'core/schedule/schedule_detail.html', {
        'schedule': sched,
        'rows': rows,
        'type_name': type_name,
        'icon': icon,
        'id': id,
        'subject_uri': subject_uri,
    })


def schedule_create(request):
    form_type = request.GET.get('type', 'Schedule')
    FormCls = {
        'Schedule': ScheduleForm,
        'Daily': DailyScheduleForm,
        'Seasonal': SeasonalScheduleForm,
        'OnDemand': OnDemandScheduleForm,
    }.get(form_type, ScheduleForm)

    if request.method == 'POST':
        form = FormCls(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            data = {
                'schedule_id': cleaned.get('schedule_id'),
                'schedule_type': form_type if form_type != 'Schedule' else '',
                'route_name': cleaned.get('route_name', ''),
                'effective_date': cleaned.get('effective_date', ''),
                'is_public': bool(cleaned.get('is_public', False)),
                'first_run_time': cleaned.get('first_run_time', ''),
                'last_run_time': cleaned.get('last_run_time', ''),
                'frequency_minutes': cleaned.get('frequency_minutes'),
                'day_of_week_mask': cleaned.get('day_of_week_mask', ''),
                'season': cleaned.get('season', ''),
                'start_date': cleaned.get('start_date', ''),
                'end_date': cleaned.get('end_date', ''),
                'operational_capacity_percentage': cleaned.get('operational_capacity_percentage'),
                'booking_lead_time_hours': cleaned.get('booking_lead_time_hours'),
                'service_window_start': cleaned.get('service_window_start', ''),
                'service_window_end': cleaned.get('service_window_end', ''),
                'max_wait_time_minutes': cleaned.get('max_wait_time_minutes'),
            }
            try:
                sid = create_schedule(data)
                messages.success(request, f"✅ Schedule {sid} created in RDF store!")
                return redirect('schedule:detail', id=sid)
            except Exception as e:
                messages.error(request, f"❌ Failed to create schedule: {e}")
    else:
        form = FormCls()
    return render(request, 'core/schedule/schedule_form.html', {
        'form': form,
        'is_update': False,
        'type': form_type,
    })


def schedule_update(request, id: str):
    subject_uri = request.GET.get('s')
    sched = get_schedule(id, subject_uri=subject_uri)
    if not sched:
        messages.error(request, f"Schedule {id} not found in RDF store.")
        return redirect('schedule:list')
    # Determine type
    tval = sched.get('type', '')
    if 'Daily' in tval:
        stype = 'Daily'
        FormCls = DailyScheduleForm
    elif 'Seasonal' in tval:
        stype = 'Seasonal'
        FormCls = SeasonalScheduleForm
    elif 'OnDemand' in tval:
        stype = 'OnDemand'
        FormCls = OnDemandScheduleForm
    else:
        stype = 'Schedule'
        FormCls = ScheduleForm
    initial = {
        'schedule_id': sched.get('scheduleID', '').split('-')[-1],
        'schedule_type': stype,
        'route_name': sched.get('routeName', ''),
        'effective_date': sched.get('effectiveDate', ''),
        'is_public': sched.get('isPublic', '').lower() == 'true',
        'first_run_time': sched.get('firstRunTime', ''),
        'last_run_time': sched.get('lastRunTime', ''),
        'frequency_minutes': sched.get('frequencyMinutes', ''),
        'day_of_week_mask': sched.get('dayOfWeekMask', ''),
        'season': sched.get('season', ''),
        'start_date': sched.get('startDate', ''),
        'end_date': sched.get('endDate', ''),
        'operational_capacity_percentage': sched.get('operationalCapacityPercentage', ''),
        'booking_lead_time_hours': sched.get('bookingLeadTimeHours', ''),
        'service_window_start': sched.get('serviceWindowStart', ''),
        'service_window_end': sched.get('serviceWindowEnd', ''),
        'max_wait_time_minutes': sched.get('maxWaitTimeMinutes', ''),
    }
    if request.method == 'POST':
        form = FormCls(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            data = {
                'schedule_id': cleaned.get('schedule_id') or id.split('-')[-1],
                'schedule_type': stype if stype != 'Schedule' else '',
                'route_name': cleaned.get('route_name', ''),
                'effective_date': cleaned.get('effective_date', ''),
                'is_public': bool(cleaned.get('is_public', False)),
                'first_run_time': cleaned.get('first_run_time', ''),
                'last_run_time': cleaned.get('last_run_time', ''),
                'frequency_minutes': cleaned.get('frequency_minutes'),
                'day_of_week_mask': cleaned.get('day_of_week_mask', ''),
                'season': cleaned.get('season', ''),
                'start_date': cleaned.get('start_date', ''),
                'end_date': cleaned.get('end_date', ''),
                'operational_capacity_percentage': cleaned.get('operational_capacity_percentage'),
                'booking_lead_time_hours': cleaned.get('booking_lead_time_hours'),
                'service_window_start': cleaned.get('service_window_start', ''),
                'service_window_end': cleaned.get('service_window_end', ''),
                'max_wait_time_minutes': cleaned.get('max_wait_time_minutes'),
            }
            try:
                update_schedule(id, data, subject_uri=subject_uri)
                messages.success(request, f"✅ Schedule {id} updated!")
                return redirect('schedule:detail', id=id)
            except Exception as e:
                messages.error(request, f"❌ Failed to update schedule: {e}")
    else:
        form = FormCls(initial=initial)
    return render(request, 'core/schedule/schedule_form.html', {
        'form': form,
        'is_update': True,
        'id': id,
        'type': stype,
        'subject_uri': subject_uri,
    })


def schedule_delete(request, id: str):
    subject_uri = request.GET.get('s')
    if request.method == 'POST':
        try:
            ok = delete_schedule(id, subject_uri=subject_uri)
            if ok:
                messages.success(request, f"✅ Schedule {id} deleted!")
            else:
                messages.warning(request, f"⚠️ Schedule {id} may not have been fully deleted.")
        except Exception as e:
            messages.error(request, f"❌ Delete error: {e}")
        return redirect('schedule:list')
    sched = get_schedule(id, subject_uri=subject_uri)
    if not sched:
        messages.error(request, f"Schedule {id} not found.")
        return redirect('schedule:list')
    return render(request, 'core/schedule/schedule_delete_confirm.html', {
        'id': id,
        'schedule': sched,
        'subject_uri': subject_uri,
    })


def schedule_ai_query(request):
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)
    payload = request.POST.dict()
    q = payload.get('query') or payload.get('q') or ''
    res = ai_generate_and_execute(q)
    return JsonResponse(res, status=200 if 'error' not in res else 400)


