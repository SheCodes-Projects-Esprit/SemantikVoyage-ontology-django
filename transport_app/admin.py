from django.contrib import admin
from .models import (
    Station, BusStop, MetroStation, TrainStation, TramStation,
    Transport, Bus, Metro, Train, Tram,
    City, Company, BusCompany, MetroCompany, Schedule, DailySchedule
)

# Enregistrer les modèles principaux
admin.site.register(City)
admin.site.register(Company)
admin.site.register(BusCompany)
admin.site.register(MetroCompany)
admin.site.register(Schedule)
admin.site.register(DailySchedule)

# Pour Station (utilisez un inline ou listez les sous-classes)
@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    list_display = ('station_name', 'located_in', 'station_accessibility')

@admin.register(MetroStation)
class MetroStationAdmin(admin.ModelAdmin):
    list_display = ('station_name', 'located_in', 'station_accessibility')

# Similaire pour les autres sous-classes de Station...

# Pour Transport
@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ('transport_line_number', 'operated_by', 'departs_from', 'arrives_at')
    search_fields = ('transport_line_number',)

@admin.register(Metro)
class MetroAdmin(admin.ModelAdmin):
    list_display = ('transport_line_number', 'operated_by', 'departs_from', 'arrives_at')

# Similaire pour Train, Tram...