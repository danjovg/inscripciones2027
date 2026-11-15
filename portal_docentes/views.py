import unicodedata
from django.shortcuts import render
from django.db.models import Q
from django.contrib.auth.decorators import login_required, user_passes_test

from inscripciones.models import Inscripcion
from personas.models import EstudianteResponsable, ContactoEmergencia
from academico.models import CarreraCuota


def _normalizar(texto):
    if not texto:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower().strip())
        if unicodedata.category(c) != 'Mn'
    )


def es_docente_autorizado(user):
    """
    Permite el acceso a los 3 usuarios del grupo 'Docentes' (y a Dirección/Secretaría/Superuser).
    Los usuarios de este grupo NO tienen acceso a portal_staff (gestion.danjo.com.gt).
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    grupos = [_normalizar(g.name) for g in user.groups.all()]
    for clave in ['docente', 'maestro', 'profesor', 'direccion', 'secretaria']:
        for g in grupos:
            if clave in g:
                return True
    return False


def limpiar_numero_wa(numero):
    """Extrae solo los dígitos para armar el enlace directo https://wa.me/..."""
    if not numero:
        return ''
    digitos = ''.join(ch for ch in str(numero) if ch.isdigit())
    if len(digitos) == 8:
        return f"502{digitos}"
    return digitos


@login_required(login_url='/accounts/login/')
@user_passes_test(es_docente_autorizado, login_url='/accounts/login/')
def directorio_alumnos(request):
    """
    Directorio de Solo Lectura para Docentes:
    Muestra únicamente Nombre del Alumno, Grado, Teléfono del Alumno y Teléfonos de Responsables
    para la creación de grupos de WhatsApp.
    """
    query = request.GET.get('q', '').strip()
    grado_id = request.GET.get('grado', '').strip()
    estado_filtro = request.GET.get('estado', 'INSCRITO').strip()

    inscripciones_qs = Inscripcion.objects.select_related(
        'estudiante', 'grado_a_cursar'
    ).order_by('grado_a_cursar__orden', 'estudiante__apellidos', 'estudiante__nombres')

    if estado_filtro == 'INSCRITO':
        inscripciones_qs = inscripciones_qs.filter(estado_solicitud='INSCRITO')
    elif estado_filtro == 'PREINSCRITO':
        inscripciones_qs = inscripciones_qs.filter(estado_solicitud='PREINSCRITO')
    else:
        inscripciones_qs = inscripciones_qs.exclude(estado_solicitud='BORRADOR')

    if grado_id:
        inscripciones_qs = inscripciones_qs.filter(grado_a_cursar_id=grado_id)

    if query:
        inscripciones_qs = inscripciones_qs.filter(
            Q(estudiante__cui__icontains=query) |
            Q(estudiante__nombres__icontains=query) |
            Q(estudiante__apellidos__icontains=query)
        )

    directorio = []
    for insc in inscripciones_qs:
        est = insc.estudiante
        vinculos = EstudianteResponsable.objects.filter(
            estudiante=est
        ).select_related('responsable').order_by('-es_contacto_principal', 'id')

        responsables_info = []
        for v in vinculos:
            r = v.responsable
            responsables_info.append({
                'nombre': f"{r.nombres} {r.apellidos}",
                'parentesco': v.parentesco,
                'es_principal': v.es_contacto_principal,
                'celular': r.celular or '',
                'wa_link': limpiar_numero_wa(r.celular),
                'tiene_whatsapp': getattr(r, 'tiene_whatsapp', True),
                'fijo': r.telefono_fijo or '',
            })

        emergencias_info = ContactoEmergencia.objects.filter(estudiante=est)

        directorio.append({
            'cui': est.cui,
            'apellidos': est.apellidos,
            'nombres': est.nombres,
            'grado': insc.grado_a_cursar,
            'estado': insc.estado_solicitud,
            'telefono_alumno': est.telefono or '',
            'wa_alumno': limpiar_numero_wa(est.telefono),
            'responsables': responsables_info,
            'emergencias': emergencias_info,
        })

    grados_disponibles = CarreraCuota.objects.filter(
        jornada__icontains='Vespertina'
    ).order_by('orden', 'nivel_educativo', 'grado')

    grado_seleccionado_obj = CarreraCuota.objects.filter(id=grado_id).first() if grado_id else None

    context = {
        'directorio': directorio,
        'grados_disponibles': grados_disponibles,
        'grado_seleccionado_obj': grado_seleccionado_obj,
        'query': query,
        'grado_filtro': grado_id,
        'estado_filtro': estado_filtro,
        'total_mostrados': len(directorio),
    }
    return render(request, 'portal_docentes/directorio.html', context)