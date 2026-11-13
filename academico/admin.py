from django.contrib import admin
from .models import CarreraCuota

@admin.register(CarreraCuota)
class CarreraCuotaAdmin(admin.ModelAdmin):
    # Columnas que se verán en la tabla general del panel
    list_display = (
        'grado', 'nivel_educativo', 'jornada', 'ciclo', 
        'cupo_maximo', 'cupos_ocupados', 'espacios_disponibles', 'orden'
    )
    
    # Filtros laterales para buscar rápidamente por año, nivel o jornada
    list_filter = ('ciclo', 'nivel_educativo', 'jornada')
    
    # Búsqueda por texto libre
    search_fields = ('grado', 'nivel_educativo', 'orientacion')
    
    # Permitir editar el límite de cupos y el orden visual directamente desde la tabla
    list_editable = ('cupo_maximo', 'orden')
    
    # Agrupar los campos en secciones lógicas dentro del formulario de edición
    fieldsets = (
        ('Información General', {
            'fields': ('ciclo', 'nivel_educativo', 'grado', 'orientacion', 'jornada', 'orden')
        }),
        ('Control de Cupos', {
            'fields': ('cupo_maximo', 'cupos_ocupados'),
            'description': "El cupo máximo define el límite. Los cupos ocupados se actualizan automáticamente al confirmar inscripciones, pero puede modificarlos manualmente en caso de error."
        }),
        ('Configuración de Formulario', {
            'fields': ('config_ingreso',)
        }),
        ('Precios Oficiales', {
            'fields': ('cuota_inscripcion', 'cuota_mensual')
        }),
    )

    # Función calculada para mostrar los espacios libres en la tabla
    def espacios_disponibles(self, obj):
        return obj.cupo_maximo - obj.cupos_ocupados
    
    # Etiqueta corta para la columna
    espacios_disponibles.short_description = "Libres"