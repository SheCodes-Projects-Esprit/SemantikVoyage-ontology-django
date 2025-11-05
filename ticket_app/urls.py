from django.urls import path
from . import views

urlpatterns = [
    # Tickets
    path('tickets/', views.list_tickets, name='list_tickets'),
    path('tickets/create/', views.create_ticket, name='create_ticket'),
    path('tickets/<int:pk>/update/', views.update_ticket, name='update_ticket'),
    path('tickets/<int:pk>/delete/', views.delete_ticket, name='delete_ticket'),
    # AI Query
    path('tickets/ai-query/', views.ticket_ai_query, name='ticket_ai_query'),
]

