from django.contrib import admin
from .models import ConfiguracionAnual, ConsentimientoConfig, CuotaMineducContrato

@admin.register(ConfiguracionAnual)
class ConfiguracionAnualAdmin(admin.ModelAdmin):
    list_display = ('anio_ciclo', 'prefijo_correlativo', 'correlativo_actual')

@admin.register(ConsentimientoConfig)
class ConsentimientoConfigAdmin(admin.ModelAdmin):
    list_display = ('ciclo', 'pregunta', 'es_obligatorio')
    list_filter = ('ciclo',)

@admin.register(CuotaMineducContrato)
class CuotaMineducContratoAdmin(admin.ModelAdmin):
    list_display = ('nivel_educacion', 'jornada', 'inscripcion', 'colegiatura_mensual', 'orden', 'ciclo')
    list_filter = ('ciclo', 'jornada')
    list_editable = ('inscripcion', 'colegiatura_mensual', 'orden')