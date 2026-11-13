from django.urls import path, include
from . import views

urlpatterns = [
    # Incluye las rutas de login/logout por defecto de Django (bajo /accounts/)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # La ruta principal del directorio de alumnos
    path('', views.directorio_alumnos, name='directorio_alumnos'),
]