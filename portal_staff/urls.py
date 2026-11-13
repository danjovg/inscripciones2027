from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('super-admin/', admin.site.urls),
    
    # Login personalizado del staff
    path('accounts/login/', auth_views.LoginView.as_view(template_name='portal_staff/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # --- ROL: AUXILIAR ---
    path('', views.dashboard_auxiliar, name='dashboard'),
    path('generar-ticket/', views.generar_ticket_rapido, name='generar_ticket_rapido'),
    
# --- ROL: DIGITADOR ---
    path('digitador/', views.panel_digitador, name='panel_digitador'),
    path('digitador/editar/<int:inscripcion_id>/', views.editar_expediente_digitador, name='editar_expediente'),
    path('digitador/contrato-pdf/<int:inscripcion_id>/', views.descargar_contrato_pdf, name='descargar_contrato_pdf'),

    # --- ROL: DIRECCIÓN ---
    path('direccion/', views.panel_direccion, name='panel_direccion'),
]