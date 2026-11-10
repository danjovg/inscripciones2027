from django.shortcuts import render, redirect
from django.db.models import Q
from personas.models import Estudiante
from inscripciones.models import Inscripcion
import random
import string


def panel_digitador(request):
    """Dashboard para que el digitador audite y complete inscripciones[cite: 6]"""
    # Filtramos alumnos que ya iniciaron proceso pero no son oficiales
    inscripciones_pendientes = Inscripcion.objects.exclude(estado_solicitud='INSCRITO')
    
    context = {
        'inscripciones': inscripciones_pendientes
    }
    return render(request, 'portal_staff/panel_digitador.html', context)

def generar_codigo_ticket():
    """Genera un código alfanumérico único para el ticket temporal"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def dashboard_auxiliar(request):
    """Vista de búsqueda para el Auxiliar"""
    query = request.GET.get('q', '')
    resultados = []
    
    if query:
        # Permiso exclusivo para buscar por CUI, nombres o apellidos
        resultados = Estudiante.objects.filter(
            Q(cui__icontains=query) | 
            Q(nombres__icontains=query) | 
            Q(apellidos__icontains=query)
        )
        
    context = {
        'resultados': resultados,
        'query': query
    }
    return render(request, 'portal_staff/dashboard.html', context)

def generar_ticket_rapido(request):
    """Crea un registro en blanco para alumnos que llegan sin preinscripción[cite: 6]"""
    if request.method == 'POST':
        cui = request.POST.get('cui')
        nombres = request.POST.get('nombres')
        
        # Crear estudiante básico
        estudiante, created = Estudiante.objects.get_or_create(
            cui=cui, 
            defaults={'nombres': nombres, 'apellidos': '', 'fecha_nacimiento': '2000-01-01', 'edad': 0}
        )
        
        # Crear inscripción en blanco con ticket
        Inscripcion.objects.create(
            estudiante=estudiante,
            estado_solicitud='TICKET GENERADO',
            ticket_generado=generar_codigo_ticket()
        )
        return redirect('dashboard')


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from inscripciones.models import Inscripcion
from portal_padres.forms import EstudianteForm, ResponsableForm
from core.models import ConfiguracionAnual

# Función temporal para el form de inscripción (luego la pasas a un forms.py del staff)
from django import forms
class InscripcionDigitadorForm(forms.ModelForm):
    class Meta:
        model = Inscripcion
        fields = ['grado_a_cursar', 'colegio_anterior']

def editar_expediente_digitador(request, inscripcion_id):
    inscripcion = get_object_or_404(Inscripcion, id=inscripcion_id)
    estudiante = inscripcion.estudiante

    # Lógica simplificada para un responsable (puedes adaptarla para múltiples)
    responsable_relacion = estudiante.estudianteresponsable_set.first()
    responsable = responsable_relacion.responsable if responsable_relacion else None

    if request.method == 'POST':
        form_estudiante = EstudianteForm(request.POST, instance=estudiante)
        form_inscripcion = InscripcionDigitadorForm(request.POST, instance=inscripcion)
        form_responsable = ResponsableForm(request.POST, instance=responsable)

        accion = request.POST.get('accion')

        if form_estudiante.is_valid() and form_inscripcion.is_valid():
            form_estudiante.save()
            form_inscripcion.save()

            if form_responsable.is_valid() and responsable:
                form_responsable.save()

            if accion == 'oficializar':
                inscripcion.estado_solicitud = 'INSCRITO'
                # Lógica para correlativo
                config = ConfiguracionAnual.objects.last()
                if config:
                    correlativo_texto = f"{config.prefijo_correlativo}{str(config.correlativo_actual).zfill(3)}-{config.anio_ciclo}"
                    # Aquí guardarías el correlativo en la inscripción (si agregas el campo)
                    config.correlativo_actual += 1
                    config.save()

                inscripcion.save()
                messages.success(request, 'Inscripción Oficializada Correctamente.')
                # Redirigir a la futura vista de impresión PDF
                return redirect('portal_staff:panel_digitador') 
            else:
                messages.success(request, 'Cambios guardados correctamente.')
                return redirect('portal_staff:editar_expediente', inscripcion_id=inscripcion.id)

    else:
        form_estudiante = EstudianteForm(instance=estudiante)
        form_inscripcion = InscripcionDigitadorForm(instance=inscripcion)
        form_responsable = ResponsableForm(instance=responsable)

    context = {
        'inscripcion': inscripcion,
        'form_estudiante': form_estudiante,
        'form_inscripcion': form_inscripcion,
        'form_responsable': form_responsable,
    }
    return render(request, 'portal_staff/panel_digitador_edicion.html', context)