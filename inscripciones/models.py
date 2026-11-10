from django.db import models
from personas.models import Estudiante
from academico.models import CarreraCuota

class Inscripcion(models.Model):
    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('PREINSCRITO', 'Preinscrito'),
        ('INSCRITO', 'Inscrito Oficialmente'),
    )
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    # CLAVE: Permitir nulos para los borradores
    grado_a_cursar = models.ForeignKey(CarreraCuota, on_delete=models.PROTECT, blank=True, null=True) 
    colegio_anterior = models.CharField(max_length=200, blank=True, null=True)
    promedio = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    razon_retiro = models.TextField(blank=True, null=True)
    estado_solicitud = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    ticket_generado = models.CharField(max_length=20, blank=True, null=True, unique=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)