from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    # Ruta restaurada para el panel de administración global (Dirección/Secretaría)
    path('super-admin/', admin.site.urls),
    
    # Rutas operativas del staff que ya creamos
    path('', views.dashboard_auxiliar, name='dashboard'),
    path('generar-ticket/', views.generar_ticket_rapido, name='generar_ticket_rapido'),
    path('digitador/', views.panel_digitador, name='panel_digitador'),
    path('digitador/editar/<int:inscripcion_id>/', views.editar_expediente_digitador, name='editar_expediente'),
]