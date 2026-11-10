from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from personas.models import Estudiante, Responsable, EstudianteResponsable
from inscripciones.models import Inscripcion
from .forms import EstudianteForm, ResponsableForm, PreinscripcionForm
import random
import string
import json
from academico.models import CarreraCuota

def generar_codigo_ticket():
    """Genera un código alfanumérico único para el ticket temporal"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def ingreso_cui(request):
    if request.method == 'POST':
        cui = request.POST.get('cui')
        if cui and len(cui) == 13:
            inscripcion_existente = Inscripcion.objects.filter(estudiante__cui=cui, estado_solicitud='INSCRITO').first()
            if inscripcion_existente:
                messages.warning(request, f'El alumno ya se encuentra inscrito oficialmente. Su código es {inscripcion_existente.ticket_generado}. Si desea realizar una modificación, acérquese al colegio.')
                return redirect('ingreso_cui')
            return redirect('formulario', cui=cui)
    return render(request, 'portal_padres/ingreso_cui.html')

def formulario_preinscripcion(request, cui):
    estudiante, created = Estudiante.objects.get_or_create(cui=cui)
    inscripcion, _ = Inscripcion.objects.get_or_create(estudiante=estudiante)
    
    # Buscamos al principal si existe para precargarlo en el formulario visible
    relacion_principal = EstudianteResponsable.objects.filter(estudiante=estudiante, es_contacto_principal=True).first()
    responsable_precargado = relacion_principal.responsable if relacion_principal else None
    
    # Cargamos responsables adicionales para mostrarlos en la UI
    otros_responsables = EstudianteResponsable.objects.filter(estudiante=estudiante)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        form_estudiante = EstudianteForm(request.POST, instance=estudiante, prefix='est')
        form_inscripcion = PreinscripcionForm(request.POST, instance=inscripcion, prefix='insc')

        # === LÓGICA CORREGIDA PARA RESPONSABLE ===
        # Obtenemos el DPI que viene del formulario POST (si existe)
        dpi_post = request.POST.get('resp-dpi')
        instancia_responsable = None
        
        # Si el DPI ya existe en la BD, se lo pasamos al formulario como instancia
        if dpi_post:
            instancia_responsable = Responsable.objects.filter(dpi=dpi_post).first()
            
        form_responsable = ResponsableForm(request.POST, instance=instancia_responsable, prefix='resp')

        # === ACCIÓN 1: GUARDAR NUEVO FAMILIAR ===
        if accion == 'guardar_familiar':
            if dpi_post and form_responsable.is_valid():
                # Al pasarle la instancia arriba, save() automáticamente sabe si hacer CREATE o UPDATE
                responsable_nuevo = form_responsable.save(commit=False)
                
                # Conversión a mayúsculas
                if responsable_nuevo.nombres: responsable_nuevo.nombres = responsable_nuevo.nombres.upper()
                if responsable_nuevo.apellidos: responsable_nuevo.apellidos = responsable_nuevo.apellidos.upper()
                if responsable_nuevo.direccion: responsable_nuevo.direccion = responsable_nuevo.direccion.upper()
                if responsable_nuevo.profesion: responsable_nuevo.profesion = responsable_nuevo.profesion.upper()
                if responsable_nuevo.nacionalidad: responsable_nuevo.nacionalidad = responsable_nuevo.nacionalidad.upper()
                if responsable_nuevo.religion: responsable_nuevo.religion = responsable_nuevo.religion.upper()
                if responsable_nuevo.iglesia: responsable_nuevo.iglesia = responsable_nuevo.iglesia.upper()
                
                responsable_nuevo.save()
                
                # Mensajes inteligentes
                if instancia_responsable:
                    messages.info(request, f'Familiar "{responsable_nuevo.nombres} {responsable_nuevo.apellidos}" ya se encontraba registrado y fue actualizado y vinculado exitosamente.')
                else:
                    messages.success(request, 'Familiar guardado exitosamente. Puede agregar otro si lo desea.')

                # Procedemos a la vinculación en la tabla intermedia (como indicaste)
                tipo_parentesco = form_responsable.cleaned_data.get('parentesco_tipo')
                EstudianteResponsable.objects.filter(estudiante=estudiante).update(es_contacto_principal=False)
                
                EstudianteResponsable.objects.update_or_create(
                    estudiante=estudiante,
                    responsable=responsable_nuevo,
                    defaults={'parentesco': tipo_parentesco, 'es_contacto_principal': True}
                )
                
                # Guardamos avances del estudiante
                if form_estudiante.is_valid():
                    estudiante_temp = form_estudiante.save(commit=False)
                    if estudiante_temp.nombres: estudiante_temp.nombres = estudiante_temp.nombres.upper()
                    if estudiante_temp.apellidos: estudiante_temp.apellidos = estudiante_temp.apellidos.upper()
                    estudiante_temp.save()

                inscripcion_temp = form_inscripcion.save(commit=False)
                inscripcion_temp.estado_solicitud = 'BORRADOR'
                inscripcion_temp.save()

                return redirect('formulario', cui=cui)
            else:
                 for field, errors in form_responsable.errors.items():
                     for error in errors:
                         messages.error(request, f'Familiar: {field} - {error}')

        # === ACCIÓN 2: GUARDAR BORRADOR O FINALIZAR ===
        elif accion in ['borrador', 'finalizar']:
            
            # Validamos qué falta para decidir si avanzar o detener el flujo
            estudiante_valido = form_estudiante.is_valid()
            inscripcion_valida = form_inscripcion.is_valid()

            if accion == 'finalizar' and not (estudiante_valido and inscripcion_valida):
                messages.error(request, 'Hay errores en el formulario del estudiante o inscripción. Revise los campos obligatorios.')
                # Si hay error al finalizar, redibujamos el formulario con los mensajes, no redirigimos
            else:
                # 1. Guardado de Estudiante y Conversión a Mayúsculas
                if estudiante_valido:
                    estudiante = form_estudiante.save(commit=False)
                    
                    if estudiante.nombres: estudiante.nombres = estudiante.nombres.upper()
                    if estudiante.apellidos: estudiante.apellidos = estudiante.apellidos.upper()
                    if estudiante.enfermedades_padece: estudiante.enfermedades_padece = estudiante.enfermedades_padece.upper()
                    if estudiante.detalle_impedimento: estudiante.detalle_impedimento = estudiante.detalle_impedimento.upper()
                    if estudiante.vive_con_otro: estudiante.vive_con_otro = estudiante.vive_con_otro.upper()
                    if estudiante.depende_de_otro: estudiante.depende_de_otro = estudiante.depende_de_otro.upper()
                    
                    if not form_estudiante.cleaned_data.get('tiene_enfermedad'):
                        estudiante.enfermedades_padece = ''
                    if not form_estudiante.cleaned_data.get('impedimento_fisico'):
                        estudiante.detalle_impedimento = ''
                    if form_estudiante.cleaned_data.get('vive_con') != 'Otro':
                        estudiante.vive_con_otro = ''
                    if form_estudiante.cleaned_data.get('depende_de') != 'Otro':
                        estudiante.depende_de_otro = ''
    
                    estudiante.save()

                # 2. Guardado de Inscripción (Datos académicos)
                if inscripcion_valida:
                    inscripcion_temp = form_inscripcion.save(commit=False)
                    inscripcion_temp.estudiante = estudiante
                    
                    # Lógica para cambiar al Encargado Principal si se seleccionó uno de la lista
                    responsable_principal_id = request.POST.get('responsable_principal')
                    if responsable_principal_id:
                        EstudianteResponsable.objects.filter(estudiante=estudiante).update(es_contacto_principal=False)
                        EstudianteResponsable.objects.filter(estudiante=estudiante, responsable__dpi=responsable_principal_id).update(es_contacto_principal=True)
    
                    if accion == 'finalizar':
                        if not inscripcion_temp.grado_a_cursar or not EstudianteResponsable.objects.filter(estudiante=estudiante).exists():
                             messages.error(request, "Debe seleccionar un grado a cursar y registrar al menos a un padre/encargado para finalizar.")
                        else:
                            inscripcion_temp.estado_solicitud = 'PREINSCRITO'
                            if not inscripcion_temp.ticket_generado:
                                inscripcion_temp.ticket_generado = generar_codigo_ticket()
                            inscripcion_temp.save()
                            return render(request, 'portal_padres/exito.html', {'ticket': inscripcion_temp.ticket_generado, 'estudiante': estudiante})
                    
                    elif accion == 'borrador':
                        inscripcion_temp.estado_solicitud = 'BORRADOR'
                        inscripcion_temp.save()
                        messages.success(request, 'Avance guardado exitosamente.')
                        return redirect('ingreso_cui')
                else:
                    if accion == 'borrador':
                         # Si es borrador pero la inscripción es inválida, forzamos un guardado parcial
                         inscripcion_temp = form_inscripcion.save(commit=False)
                         inscripcion_temp.estado_solicitud = 'BORRADOR'
                         inscripcion_temp.save()
                         messages.success(request, 'Avance guardado exitosamente (algunos datos están incompletos).')
                         return redirect('ingreso_cui')

    # GET request o Formulario Inválido (recarga con errores)
    form_estudiante = EstudianteForm(instance=estudiante, prefix='est')
    form_responsable = ResponsableForm(prefix='resp') # Formulario vacío para agregar uno nuevo
    form_inscripcion = PreinscripcionForm(instance=inscripcion, prefix='insc')

    grados_ordenados = CarreraCuota.objects.all().order_by('orden', 'nivel_educativo', 'grado')
    config_grados = {str(grado.id): grado.config_ingreso for grado in grados_ordenados}

    # Recargamos responsables adicionales para mostrarlos siempre actualizados en la UI
    otros_responsables = EstudianteResponsable.objects.filter(estudiante=estudiante)

    context = {
        'cui': cui,
        'form_estudiante': form_estudiante,
        'form_responsable': form_responsable,
        'form_inscripcion': form_inscripcion,
        'otros_responsables': otros_responsables,
        'config_grados_json': json.dumps(config_grados),
    }
    return render(request, 'portal_padres/formulario.html', context)

def buscar_dpi_ajax(request, dpi):
    try:
        responsable = Responsable.objects.get(dpi=dpi)
        data = {
            'existe': True,
            'nombres': responsable.nombres,
            'apellidos': responsable.apellidos,
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