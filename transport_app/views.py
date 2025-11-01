# transport_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Station, Transport, BusStop, MetroStation, TrainStation, TramStation, Bus, Metro, Train, Tram
from .forms import StationForm, TransportForm


# ==================== STATIONS ====================
def list_stations(request):
    stations = []
    for subclass in Station.__subclasses__():
        qs = subclass.objects.select_related('located_in')
        for obj in qs:
            # Récupère tous les transports liés via related_name
            transports = set()
            for transport_cls in Transport.__subclasses__():
                departures = getattr(obj, f'{transport_cls.__name__.lower()}_departures', None)
                arrivals = getattr(obj, f'{transport_cls.__name__.lower()}_arrivals', None)
                if departures:
                    transports.update(departures.all())
                if arrivals:
                    transports.update(arrivals.all())
            obj.get_all_transports = transports
            stations.append(obj)
    return render(request, 'list_stations.html', {'stations': stations})

def create_station(request):
    if request.method == 'POST':
        form = StationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Station créée avec succès !")
            return redirect('list_stations')
    else:
        form = StationForm()
    return render(request, 'station_form.html', {'form': form, 'title': 'Créer une Station'})


# update_station
def update_station(request, pk):
    station = get_object_or_404(Station, pk=pk)
    if request.method == 'POST':
        form = StationForm(request.POST, instance=station)
        if form.is_valid():
            form.save()
            messages.success(request, "Station modifiée !")
            return redirect('list_stations')
    else:
        form = StationForm(instance=station)
    return render(request, 'station_form.html', {
        'form': form,
        'title': 'Modifier la Station'
    })

# delete_station
def delete_station(request, pk):
    station = get_object_or_404(Station, pk=pk)
    if request.method == 'POST':
        station.delete()
        messages.success(request, "Station supprimée.")
        return redirect('list_stations')
    return render(request, 'confirm_delete.html', {
        'object': station,
        'type': 'station'
    })

# ==================== TRANSPORTS ====================
def list_transports(request):
    transports = []
    for subclass in Transport.__subclasses__():
        transports.extend(subclass.objects.all())
    return render(request, 'transports_list.html', {'transports': transports})


def create_transport(request):
    if request.method == 'POST':
        form = TransportForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Transport créé avec succès !")
                return redirect('list_transports')
            except ValidationError:
                pass
    else:
        form = TransportForm()
    return render(request, 'transport_form.html', {'form': form, 'title': 'Créer un Transport'})


def update_transport(request, pk, model_name):
    model_map = {'bus': Bus, 'metro': Metro, 'train': Train, 'tram': Tram}
    if model_name.lower() not in model_map:
        messages.error(request, "Type de transport invalide.")
        return redirect('list_transports')

    model = model_map[model_name.lower()]
    transport = get_object_or_404(model, pk=pk)

    if request.method == 'POST':
        form = TransportForm(request.POST, instance=transport)
        if form.is_valid():
            new_line = form.cleaned_data['transport_line_number']
            if Transport.objects.exclude(pk=transport.pk).filter(transport_line_number=new_line).exists():
                form.add_error('transport_line_number', 'Cette ligne existe déjà.')
            else:
                try:
                    form.save()
                    messages.success(request, "Transport modifié avec succès !")
                    return redirect('list_transports')
                except ValidationError:
                    pass
    else:
        form = TransportForm(instance=transport)

    return render(request, 'transport_form.html', {'form': form, 'title': 'Modifier le Transport'})


def delete_transport(request, pk, model_name):
    model_map = {'bus': Bus, 'metro': Metro, 'train': Train, 'tram': Tram}
    if model_name.lower() not in model_map:
        messages.error(request, "Type de transport invalide.")
        return redirect('list_transports')

    model = model_map[model_name.lower()]
    transport = get_object_or_404(model, pk=pk)

    if request.method == 'POST':
        transport.delete()
        messages.success(request, "Transport supprimé.")
        return redirect('list_transports')

    return render(request, 'confirm_delete.html', {'object': transport, 'type': 'transport'})