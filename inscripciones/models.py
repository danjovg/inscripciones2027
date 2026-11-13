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
    grado_a_cursar = models.ForeignKey(CarreraCuota, on_delete=models.PROTECT, blank=True, null=True)
    colegio_anterior = models.CharField(max_length=200, blank=True, null=True)
    promedio = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    razon_retiro = models.TextField(blank=True, null=True)
    estado_solicitud = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    ticket_generado = models.CharField(max_length=20, blank=True, null=True, unique=True)
    correlativo_contrato = models.CharField(max_length=30, blank=True, null=True, verbose_name="Correlativo Oficial de Contrato")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.estudiante} - {self.estado_solicitud}"