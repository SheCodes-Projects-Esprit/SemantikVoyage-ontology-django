from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    path('', views.schedule_list, name='list'),
    path('create/', views.schedule_create, name='create'),
    path('ai-query/', views.schedule_ai_query, name='ai_query'),
    path('<str:id>/', views.schedule_detail, name='detail'),
    path('<str:id>/update/', views.schedule_update, name='update'),
    path('<str:id>/delete/', views.schedule_delete, name='delete'),
]


