from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from personas.models import Estudiante, Responsable, EstudianteResponsable
from inscripciones.models import Inscripcion
from .forms import EstudianteForm, ResponsableForm, PreinscripcionForm
import random
import string
import json
import re
from academico.models import CarreraCuota


def generar_codigo_ticket():
    """Genera un código alfanumérico único para el ticket temporal"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def ingreso_cui(request):
    if request.method == 'POST':
        cui_raw = request.POST.get('cui', '')
        cui = re.sub(r'[\s\-]+', '', cui_raw)  # Quita espacios o guiones si el padre pegó el CUI
        if cui and len(cui) == 13:
            inscripcion_existente = Inscripcion.objects.filter(
                estudiante__cui=cui,
                estado_solicitud='INSCRITO'
            ).first()
            if inscripcion_existente:
                messages.warning(
                    request,
                    f'El alumno ya se encuentra inscrito oficialmente (Correlativo/Ticket: {inscripcion_existente.correlativo_contrato or inscripcion_existente.ticket_generado}). Si desea realizar una modificación, acérquese al colegio.'
                )
                return redirect('ingreso_cui')
            return redirect('formulario', cui=cui)
        else:
            messages.error(request, 'Por favor ingrese un número de CUI válido de 13 dígitos.')
    return render(request, 'portal_padres/ingreso_cui.html')


def formulario_preinscripcion(request, cui):
    estudiante, created = Estudiante.objects.get_or_create(cui=cui)
    inscripcion, _ = Inscripcion.objects.get_or_create(estudiante=estudiante)

    if inscripcion.estado_solicitud == 'INSCRITO':
        return redirect('alumno_inscrito', cui=cui)

    # Asegurar que siempre tenga su ticket temporal desde el inicio
    if not inscripcion.ticket_generado:
        inscripcion.ticket_generado = generar_codigo_ticket()
        inscripcion.save(update_fields=['ticket_generado'])

    # Buscamos al principal si existe
    relacion_principal = EstudianteResponsable.objects.filter(estudiante=estudiante, es_contacto_principal=True).first()
    responsable_precargado = relacion_principal.responsable if relacion_principal else None

    otros_responsables = EstudianteResponsable.objects.filter(estudiante=estudiante)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        form_estudiante = EstudianteForm(request.POST, instance=estudiante, prefix='est')
        form_inscripcion = PreinscripcionForm(request.POST, instance=inscripcion, prefix='insc')

        # Limpiar espacios o guiones en el DPI del responsable si fue ingresado
        dpi_raw = request.POST.get('resp-dpi', '')
        dpi_post = re.sub(r'[\s\-]+', '', dpi_raw) if dpi_raw else ''
        instancia_responsable = None

        if dpi_post:
            instancia_responsable = Responsable.objects.filter(dpi=dpi_post).first()

        post_data = request.POST.copy()
        if dpi_post:
            post_data['resp-dpi'] = dpi_post

        form_responsable = ResponsableForm(post_data, instance=instancia_responsable, prefix='resp')

        # Función auxiliar para guardar avances del estudiante e inscripción sin perder nada
        def guardar_datos_alumno_e_inscripcion(estado_destino):
            if form_estudiante.is_valid():
                est_obj = form_estudiante.save(commit=False)
                if est_obj.nombres: est_obj.nombres = est_obj.nombres.upper()
                if est_obj.apellidos: est_obj.apellidos = est_obj.apellidos.upper()
                if est_obj.enfermedades_padece: est_obj.enfermedades_padece = est_obj.enfermedades_padece.upper()
                if est_obj.detalle_impedimento: est_obj.detalle_impedimento = est_obj.detalle_impedimento.upper()
                if est_obj.vive_con_otro: est_obj.vive_con_otro = est_obj.vive_con_otro.upper()
                if est_obj.depende_de_otro: est_obj.depende_de_otro = est_obj.depende_de_otro.upper()

                if not form_estudiante.cleaned_data.get('tiene_enfermedad'):
                    est_obj.enfermedades_padece = ''
                if not form_estudiante.cleaned_data.get('impedimento_fisico'):
                    est_obj.detalle_impedimento = ''
                if form_estudiante.cleaned_data.get('vive_con') != 'Otro':
                    est_obj.vive_con_otro = ''
                if form_estudiante.cleaned_data.get('depende_de') != 'Otro':
                    est_obj.depende_de_otro = ''
                est_obj.save()
            else:
                # Guardado parcial de emergencia si algún campo opcional dio error
                nombres_raw = (request.POST.get('est-nombres') or '').strip().upper()
                apellidos_raw = (request.POST.get('est-apellidos') or '').strip().upper()
                if nombres_raw: estudiante.nombres = nombres_raw
                if apellidos_raw: estudiante.apellidos = apellidos_raw
                estudiante.save()

            if form_inscripcion.is_valid():
                insc_obj = form_inscripcion.save(commit=False)
            else:
                insc_obj = inscripcion
                grado_id = request.POST.get('insc-grado_a_cursar')
                if grado_id and str(grado_id).isdigit():
                    insc_obj.grado_a_cursar_id = int(grado_id)

            insc_obj.estudiante = estudiante
            if not insc_obj.ticket_generado:
                insc_obj.ticket_generado = generar_codigo_ticket()
            insc_obj.estado_solicitud = estado_destino
            insc_obj.save()

            responsable_principal_id = request.POST.get('responsable_principal')
            if responsable_principal_id:
                EstudianteResponsable.objects.filter(estudiante=estudiante).update(es_contacto_principal=False)
                EstudianteResponsable.objects.filter(estudiante=estudiante, responsable__dpi=responsable_principal_id).update(es_contacto_principal=True)

            return insc_obj

        # Función auxiliar para guardar al familiar si llenaron DPI en la Sección 3
        def intentar_guardar_familiar():
            if dpi_post and form_responsable.is_valid():
                responsable_nuevo = form_responsable.save(commit=False)
                if responsable_nuevo.nombres: responsable_nuevo.nombres = responsable_nuevo.nombres.upper()
                if responsable_nuevo.apellidos: responsable_nuevo.apellidos = responsable_nuevo.apellidos.upper()
                if responsable_nuevo.direccion: responsable_nuevo.direccion = responsable_nuevo.direccion.upper()
                if responsable_nuevo.profesion: responsable_nuevo.profesion = responsable_nuevo.profesion.upper()
                if responsable_nuevo.nacionalidad: responsable_nuevo.nacionalidad = responsable_nuevo.nacionalidad.upper()
                if responsable_nuevo.religion: responsable_nuevo.religion = responsable_nuevo.religion.upper()
                if responsable_nuevo.iglesia: responsable_nuevo.iglesia = responsable_nuevo.iglesia.upper()
                responsable_nuevo.save()

                tipo_parentesco = form_responsable.cleaned_data.get('parentesco_tipo') or 'Encargado'
                EstudianteResponsable.objects.filter(estudiante=estudiante).update(es_contacto_principal=False)
                EstudianteResponsable.objects.update_or_create(
                    estudiante=estudiante,
                    responsable=responsable_nuevo,
                    defaults={'parentesco': tipo_parentesco, 'es_contacto_principal': True}
                )
                return True, responsable_nuevo
            return False, None

        # === ACCIÓN 1: BOTÓN SECUNDARIO "GUARDAR NUEVO FAMILIAR" ===
        if accion == 'guardar_familiar':
            exito_fam, resp_obj = intentar_guardar_familiar()
            if exito_fam:
                guardar_datos_alumno_e_inscripcion(inscripcion.estado_solicitud or 'PREINSCRITO')
                if instancia_responsable:
                    messages.info(request, f'Familiar "{resp_obj.nombres} {resp_obj.apellidos}" actualizado y vinculado exitosamente.')
                else:
                    messages.success(request, 'Familiar guardado y vinculado exitosamente.')
                return redirect('formulario', cui=cui)
            else:
                for field, errors in form_responsable.errors.items():
                    for error in errors:
                        messages.error(request, f'Familiar ({field}): {error}')

        # === ACCIÓN 2: BOTÓN PRINCIPAL UNIFICADO DE GUARDAR CAMBIOS ===
        elif accion in ['borrador', 'finalizar', 'guardar_todo']:
            # Si el padre dejó escrito un DPI en la sección 3 sin darle a "Guardar Familiar", lo guardamos automáticamente
            if dpi_post:
                intentar_guardar_familiar()

            inscripcion_actualizada = guardar_datos_alumno_e_inscripcion('PREINSCRITO')
            return render(
                request,
                'portal_padres/exito.html',
                {
                    'ticket': inscripcion_actualizada.ticket_generado,
                    'estudiante': estudiante,
                }
            )

    # GET request
    form_estudiante = EstudianteForm(instance=estudiante, prefix='est')
    form_responsable = ResponsableForm(prefix='resp')
    form_inscripcion = PreinscripcionForm(instance=inscripcion, prefix='insc')

    grados_ordenados = CarreraCuota.objects.all().order_by('orden', 'nivel_educativo', 'grado')
    config_grados = {str(grado.id): grado.config_ingreso for grado in grados_ordenados}
    otros_responsables = EstudianteResponsable.objects.filter(estudiante=estudiante)

    context = {
        'cui': cui,
        'inscripcion': inscripcion,
        'form_estudiante': form_estudiante,
        'form_responsable': form_responsable,
        'form_inscripcion': form_inscripcion,
        'otros_responsables': otros_responsables,
        'config_grados_json': json.dumps(config_grados),
    }
    return render(request, 'portal_padres/formulario.html', context)


def buscar_dpi_ajax(request, dpi):
    dpi_limpio = re.sub(r'[\s\-]+', '', dpi or '')
    try:
        responsable = Responsable.objects.get(dpi=dpi_limpio)
        data = {
            'existe': True,
            'nombres': responsable.nombres,
            'apellidos': responsable.apellidos,
            'edad': responsable.edad,
            'estado_civil': responsable.estado_civil,
            'direccion': responsable.direccion,
            'celular': responsable.celular,
            'telefono_fijo': responsable.telefono_fijo,
            'profesion': responsable.profesion,
            'nacionalidad': responsable.nacionalidad,
            'religion': responsable.religion,
            'iglesia': responsable.iglesia,
            'correo_electronico': responsable.correo_electronico,
            'tiene_whatsapp': responsable.tiene_whatsapp,
        }
    except Responsable.DoesNotExist:
        data = {'existe': False}

    return JsonResponse(data)


def alumno_inscrito(request, cui):
    """Vista de solo lectura para expedientes ya oficializados por los digitadores."""
    inscripcion = get_object_or_404(Inscripcion, estudiante__cui=cui, estado_solicitud='INSCRITO')

    context = {
        'inscripcion': inscripcion,
        'estudiante': inscripcion.estudiante,
    }
    return render(request, 'portal_padres/alumno_inscrito.html', context)