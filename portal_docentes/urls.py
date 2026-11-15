from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Login exclusivo y con identidad propia para Docentes
    path('accounts/login/', auth_views.LoginView.as_view(template_name='portal_docentes/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),

    # Directorio de alumnos y teléfonos para grupos de WhatsApp
    path('', views.directorio_alumnos, name='directorio_alumnos'),
]