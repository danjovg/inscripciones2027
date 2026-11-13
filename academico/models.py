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

    # --- CAMPOS DE CONTROL DE CUPOS AÑADIDOS ---
    cupo_maximo = models.PositiveIntegerField(
        default=30, 
        help_text="Cantidad máxima de alumnos permitidos para firmar contrato en este grado."
    )
    cupos_ocupados = models.PositiveIntegerField(
        default=0, 
        help_text="Se incrementa/decrementa automáticamente cuando un digitador aprueba/cambia una inscripción."
    )

    class Meta:
        ordering = ['orden', 'nivel_educativo', 'grado'] # Ordenamiento automático por defecto

    def __str__(self):
        orientacion_str = f" {self.orientacion}" if self.orientacion else ""
        return f"{self.grado} {self.nivel_educativo}{orientacion_str} - {self.jornada} ({self.ciclo.anio_ciclo})"
    
    # --- PROPIEDAD PARA VERIFICAR DISPONIBILIDAD (USADA EN VIEWS) ---
    @property
    def hay_cupo(self):
        """Verifica si aún quedan espacios en el grado."""
        return self.cupos_ocupados < self.cupo_maximo