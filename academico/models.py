from django.db import models
from core.models import ConfiguracionAnual

class CarreraCuota(models.Model):
    COMPORTAMIENTO_INGRESO = (
        ('OBLIGATORIO', 'Siempre pedir Colegio Anterior (Ej. 1ro Básico)'),
        ('MANUAL', 'Mostrar Checkbox Opcional (Ej. 4to PAE, 2do Básico)'),
        ('OCULTO', 'Nunca pedir (Exclusivo Reingreso)'),
    )
    ciclo = models.ForeignKey(ConfiguracionAnual, on_delete=models.CASCADE)
    orden = models.IntegerField(default=0, help_text="1, 2, 3... para ordenar el listado visualmente")
    config_ingreso = models.CharField(max_length=20, choices=COMPORTAMIENTO_INGRESO, default='MANUAL')
    
    nivel_educativo = models.CharField(max_length=50)
    grado = models.CharField(max_length=50)
    orientacion = models.CharField(max_length=100, blank=True, null=True)
    jornada = models.CharField(max_length=50)
    cuota_inscripcion = models.DecimalField(max_digits=8, decimal_places=2)
    cuota_mensual = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ['orden', 'nivel_educativo', 'grado'] # Ordenamiento automático por defecto

    def __str__(self):
        return f"{self.grado} {self.nivel_educativo} - {self.jornada}"