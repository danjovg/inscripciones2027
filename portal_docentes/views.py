from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from inscripciones.models import Inscripcion

@login_required
def directorio_alumnos(request):
    query = request.GET.get('q', '').strip()
    
    # REGLA ESTRICTA: Solo alumnos formalmente inscritos.
    # Buscamos 'inscrito' pero EXCLUIMOS a los 'preinscrito'
    inscripciones = Inscripcion.objects.filter(
        estado_solicitud__icontains='inscrito'
    ).exclude(
        estado_solicitud__icontains='preinscrito'
    )

# Al final de la función directorio_alumnos, antes del context = ...
# ... código anterior ...
    if query:
        inscripciones = inscripciones.filter(
            Q(estudiante__cui__icontains=query) |
            Q(estudiante__nombres__icontains=query) |
            Q(estudiante__apellidos__icontains=query) |
            Q(ticket_generado__icontains=query)
        )

    # ORDENAR ALFABÉTICAMENTE POR APELLIDO Y LUEGO NOMBRE
    inscripciones = inscripciones.order_by('estudiante__apellidos', 'estudiante__nombres')

    context = {
        'inscripciones': inscripciones,
        'query': query,
    }
    return render(request, 'portal_docentes/directorio.html', context)