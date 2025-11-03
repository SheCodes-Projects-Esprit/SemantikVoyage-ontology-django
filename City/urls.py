# urls.py
from django.urls import path
from . import views

app_name = 'city'
urlpatterns = [
    path('', views.city_list, name='list'),
    path('create/', views.city_create, name='create'),
    path('<str:name>/', views.city_detail, name='detail'),
    path('<str:name>/update/', views.city_update, name='update'),
    path('<str:name>/delete/', views.city_delete, name='delete'),
]