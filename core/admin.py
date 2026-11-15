from django.contrib import admin
from .models import (
    ConfiguracionAnual,
    ConsentimientoConfig,
    CuotaMineducContrato,
    ControlEstadoSistema,
)

@admin.register(ConfiguracionAnual)
class ConfiguracionAnualAdmin(admin.ModelAdmin):
    list_display = ('anio_ciclo', 'prefijo_correlativo', 'correlativo_actual')

@admin.register(ConsentimientoConfig)
class ConsentimientoConfigAdmin(admin.ModelAdmin):
    list_display = ('ciclo', 'pregunta', 'es_obligatorio')
    list_filter = ('ciclo',)

@admin.register(CuotaMineducContrato)
class CuotaMineducContratoAdmin(admin.ModelAdmin):
    list_display = (
        'orden',
        'nivel_educacion',
        'jornada',
        'inscripcion_colegio',
        'mensualidad_colegio',
        'inscripcion',
        'colegiatura_mensual',
        'ciclo',
    )
    list_display_links = ('nivel_educacion',)
    list_filter = ('ciclo', 'jornada')
    list_editable = (
        'orden',
        'inscripcion_colegio',
        'mensualidad_colegio',
        'inscripcion',
        'colegiatura_mensual',
    )


@admin.register(ControlEstadoSistema)
class ControlEstadoSistemaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre_control',
        'bloqueo_por_pago',
        'cierre_jornada_laboral',
        'permitir_direccion_en_cierre',
        'horario_atencion_texto',
        'ultima_modificacion',
    )
    list_editable = (
        'bloqueo_por_pago',
        'cierre_jornada_laboral',
        'permitir_direccion_en_cierre',
    )

    def has_add_permission(self, request):
        # Evita crear múltiples filas; solo existirá 1 panel maestro de control
        if ControlEstadoSistema.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False