from django.urls import path
from . import views

urlpatterns = [
    # Stations
    path('stations/', views.list_stations, name='list_stations'),
    path('stations/create/', views.create_station, name='create_station'),
    path('stations/<int:pk>/update/', views.update_station, name='update_station'),
    path('stations/<int:pk>/delete/', views.delete_station, name='delete_station'),
    
    # Transports
    path('transports/', views.list_transports, name='list_transports'),
    path('transports/create/', views.create_transport, name='create_transport'),
    path('transports/<int:pk>/<str:model_name>/update/', views.update_transport, name='update_transport'),
    path('transports/<int:pk>/<str:model_name>/delete/', views.delete_transport, name='delete_transport'),
    
    # Ontology
    path('ontology/query/', views.ontology_query_view, name='ontology_query'),
    path('ontology/sync/', views.sync_all_data_view, name='sync_ontology'),
    path('ontology/status/', views.ontology_status_view, name='ontology_status'),
]