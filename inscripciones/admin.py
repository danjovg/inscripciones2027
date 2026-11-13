from django.contrib import admin
from .models import Inscripcion

@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    # Usamos los campos exactos que definiste en tu models.py
    list_display = ('estudiante', 'grado_a_cursar', 'estado_solicitud', 'ticket_generado', 'fecha_registro')
    
    # Filtramos por el estado y por el grado
    list_filter = ('estado_solicitud', 'grado_a_cursar')
    
    # Búsqueda por el CUI o nombre del estudiante, y por el ticket
    search_fields = ('estudiante__cui', 'estudiante__nombres', 'estudiante__apellidos', 'ticket_generado')
    
    # Campos que no se deben editar manualmente en el admin
    readonly_fields = ('ticket_generado', 'fecha_registro')