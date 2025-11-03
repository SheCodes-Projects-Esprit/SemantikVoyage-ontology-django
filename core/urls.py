from django.urls import path , include
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('query/', views.query_view, name='query'),
    path('load-ontology/', views.load_ontology, name='load_ontology'),
    path('debug-fuseki/', views.debug_fuseki, name='debug_fuseki'),
    path('itinerary/', include('itinerary.urls')),
    path('city/', include('city.urls')),
    path('company/', include('company.urls')),
]