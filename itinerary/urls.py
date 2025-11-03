from django.urls import path
from . import views

app_name = 'itinerary'  # For namespacing

urlpatterns = [
    path('', views.itinerary_list, name='list'),
    # IMPORTANT: Put specific paths BEFORE the generic <str:id> pattern
    path('create/', views.itinerary_create, name='create'),
    path('ai-suggest/', views.itinerary_ai_suggest, name='ai_suggest'),  # MOVED BEFORE <str:id>
    path('ai-query/', views.itinerary_ai_query, name='ai_query'),
    # Generic patterns at the end
    path('<str:id>/', views.itinerary_detail, name='detail'),
    path('<str:id>/update/', views.itinerary_update, name='update'),
    path('<str:id>/delete/', views.itinerary_delete, name='delete'),
   
]