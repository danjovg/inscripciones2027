from django.db import models

class ConfiguracionAnual(models.Model):
    anio_ciclo = models.IntegerField(unique=True) # Ej. 2027
    datos_representante_legal = models.TextField(help_text="Nombres, DPI, Edad, Estado Civil, Profesión, Dirección, Datos de Notario y Partida")
    texto_resolucion_diaco = models.CharField(max_length=200, blank=True, null=True)
    monto_mora = models.DecimalField(max_digits=8, decimal_places=2, default=10.00)
    plantilla_contrato_html = models.TextField()
    prefijo_correlativo = models.CharField(max_length=10, default="CA-")
    correlativo_actual = models.IntegerField(default=1)

    def __str__(self):
        return f"Ciclo Escolar {self.anio_ciclo}"

class ConsentimientoConfig(models.Model):
    ciclo = models.ForeignKey(ConfiguracionAnual, on_delete=models.CASCADE)
    pregunta = models.CharField(max_length=200) # Ej. "Autorizo uso de imagen"
    es_obligatorio = models.BooleanField(default=True)

    def __str__(self):
        return self.pregunta