from django.contrib import admin
from .models import Estudiante, Responsable, EstudianteResponsable, ContactoEmergencia

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('cui', 'nombres', 'apellidos', 'edad', 'telefono')
    search_fields = ('cui', 'nombres', 'apellidos')

@admin.register(Responsable)
class ResponsableAdmin(admin.ModelAdmin):
    list_display = ('dpi', 'nombres', 'apellidos', 'celular', 'profesion')
    search_fields = ('dpi', 'nombres', 'apellidos')

@admin.register(EstudianteResponsable)
class EstudianteResponsableAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'responsable', 'parentesco', 'es_contacto_principal')
    list_filter = ('es_contacto_principal', 'parentesco')
    search_fields = ('estudiante__nombres', 'responsable__nombres')

admin.site.register(ContactoEmergencia)