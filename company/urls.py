# company/urls.py
from django.urls import path
from . import views

app_name = 'company'
urlpatterns = [
    path('', views.company_list, name='list'),
    path('ai/', views.company_ai_query, name='ai'),
    path('debug/', views.company_debug, name='debug'),
    path('create/', views.company_create, name='create'),
    path('<str:name>/', views.company_detail, name='detail'),
    path('<str:name>/update/', views.company_update, name='update'),
    path('<str:name>/delete/', views.company_delete, name='delete'),
]