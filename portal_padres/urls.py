from django.urls import path
from . import views

urlpatterns = [
    path('', views.ingreso_cui, name='ingreso_cui'),
    path('formulario/<str:cui>/', views.formulario_preinscripcion, name='formulario'),
    path('inscrito/<str:cui>/', views.alumno_inscrito, name='alumno_inscrito'),
    path('api/buscar-dpi/<str:dpi>/', views.buscar_dpi_ajax, name='buscar_dpi'),
]