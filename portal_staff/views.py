import base64
import csv
import json
import os
import random
import re
import string
import unicodedata
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse

from academico.models import CarreraCuota
from core.models import ConfiguracionAnual, CuotaMineducContrato
from inscripciones.models import Inscripcion
from personas.models import (
    ContactoEmergencia,
    Estudiante,
    EstudianteResponsable,
    Responsable,
)
from portal_padres.forms import EstudianteForm, ResponsableForm


# =========================================================================
# VALIDADORES DE PERMISOS POR ROL (INSENSIBLES A TILDES Y MAYÚSCULAS)
# =========================================================================
def _normalizar_texto(texto):
    """Elimina tildes y pasa a minúsculas para que 'Dirección' y 'Direccion' coincidan siempre."""
    if not texto:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower().strip())
        if unicodedata.category(c) != 'Mn'
    )


def usuario_tiene_rol(user, palabras_clave):
    """Verifica si el usuario pertenece a alguno de los grupos indicados (con o sin tilde)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    grupos_usuario = [_normalizar_texto(g.name) for g in user.groups.all()]
    for clave in palabras_clave:
        clave_norm = _normalizar_texto(clave)
        for grupo in grupos_usuario:
            if clave_norm in grupo:
                return True
    return False


def es_personal_administrativo(user):
    """Permite entrar al portal a cualquier usuario con al menos uno de los 4 roles administrativos."""
    return usuario_tiene_rol(user, ['auxiliar', 'digitador', 'secretaria', 'direccion'])


def es_auxiliar_o_autorizado(user):
    """Valida si tiene asignado el grupo Auxiliares."""
    return usuario_tiene_rol(user, ['auxiliar'])


def es_digitador_o_superior(user):
    """Valida si tiene asignado el grupo Digitadores, Secretaría o Dirección."""
    return usuario_tiene_rol(user, ['digitador', 'secretaria', 'direccion'])


def es_secretaria_o_superior(user):
    """Valida si tiene asignado el grupo Secretaría General o Dirección."""
    return usuario_tiene_rol(user, ['secretaria', 'direccion'])


def es_direccion(user):
    """Valida si tiene asignado el grupo Dirección (con o sin tilde)."""
    return usuario_tiene_rol(user, ['direccion'])


def es_superusuario_exclusivo(user):
    """Bloquea a todos los roles excepto al Supervisor (Superusuario)."""
    return user.is_authenticated and user.is_superuser


# =========================================================================
# FUNCIONES AUXILIARES GLOBALES
# =========================================================================
def generar_codigo_ticket():
    """Genera un código alfanumérico único de 6 caracteres para el ticket interno."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def construir_correlativo_oficial(config, grado):
    """
    Construye el correlativo oficial con el formato: CA-002-JV-2027 o CA-002-JM-2027
    """
    prefijo = config.prefijo_correlativo.strip() if (config and config.prefijo_correlativo) else "CA-"
    if not prefijo.endswith('-'):
        prefijo = f"{prefijo}-"

    numero = str(config.correlativo_actual if config else 1).zfill(3)
    anio = config.anio_ciclo if config else 2027

    jornada_txt = (grado.jornada or '').upper() if grado else ''
    if 'MATUTINA' in jornada_txt or jornada_txt == 'JM':
        sigla_jornada = 'JM'
    elif 'VESPERTINA' in jornada_txt or jornada_txt == 'JV':
        sigla_jornada = 'JV'
    else:
        sigla_jornada = 'JV'

    return f"{prefijo}{numero}-{sigla_jornada}-{anio}"


# =========================================================================
# VISTAS DEL ROL: AUXILIAR (PUERTA Y ENRUTAMIENTO POR ROL)
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_personal_administrativo, login_url='/accounts/login/')
def dashboard_auxiliar(request):
    """
    Vista raíz (/):
    - Si el usuario NO tiene el rol de Auxiliar, lo redirige automáticamente a su módulo
      correspondiente (Secretaría, Dirección o Digitador).
    - Si es Auxiliar (o Superuser), muestra el buscador de Puerta.
    """
    if not es_auxiliar_o_autorizado(request.user):
        if es_secretaria_o_superior(request.user) and not es_direccion(request.user):
            return redirect('panel_secretaria')
        if es_direccion(request.user):
            return redirect('panel_direccion')
        if es_digitador_o_superior(request.user):
            return redirect('panel_digitador')
        return redirect('/accounts/login/')

    query = request.GET.get('q', '').strip()
    query_limpio = re.sub(r'[\s\-]+', '', query)
    resultados = []

    if query:
        q_filter = (
            Q(cui__icontains=query) |
            Q(nombres__icontains=query) |
            Q(apellidos__icontains=query)
        )
        if query_limpio and query_limpio != query:
            q_filter |= Q(cui__icontains=query_limpio)
        resultados = Estudiante.objects.filter(q_filter)

    context = {
        'resultados': resultados,
        'query': query,
    }
    return render(request, 'portal_staff/dashboard.html', context)


@login_required(login_url='/accounts/login/')
@user_passes_test(es_auxiliar_o_autorizado, login_url='/accounts/login/')
def generar_ticket_rapido(request):
    """Crea un expediente rápido en BORRADOR y registra qué Auxiliar lo emitió."""
    if request.method == 'POST':
        cui_raw = request.POST.get('cui', '').strip()
        cui = re.sub(r'[\s\-]+', '', cui_raw)
        nombres = request.POST.get('nombres', '').strip().upper()
        apellidos = request.POST.get('apellidos', '').strip().upper()

        estudiante, created = Estudiante.objects.get_or_create(
            cui=cui,
            defaults={
                'nombres': nombres,
                'apellidos': apellidos,
                'fecha_nacimiento': date(2000, 1, 1),
                'edad': 0,
            }
        )

        inscripcion, insc_created = Inscripcion.objects.get_or_create(
            estudiante=estudiante,
            defaults={
                'estado_solicitud': 'BORRADOR',
                'ticket_generado': generar_codigo_ticket(),
                'creado_por_auxiliar': request.user,
            }
        )

        if not inscripcion.ticket_generado:
            inscripcion.ticket_generado = generar_codigo_ticket()
        if not inscripcion.creado_por_auxiliar:
            inscripcion.creado_por_auxiliar = request.user
        inscripcion.save()

        return redirect(f"/?q={cui}")

    return redirect('dashboard')


# =========================================================================
# FORMULARIOS EXCLUSIVOS DEL DIGITADOR
# =========================================================================
class InscripcionDigitadorForm(forms.ModelForm):
    es_nuevo_ingreso = forms.BooleanField(
        required=False,
        label="¿Es estudiante de Primer Ingreso al colegio?",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Inscripcion
        fields = ['grado_a_cursar', 'es_nuevo_ingreso', 'colegio_anterior', 'promedio', 'razon_retiro']
        widgets = {
            'grado_a_cursar': forms.Select(attrs={'class': 'form-select border-primary'}),
            'colegio_anterior': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre oficial del establecimiento anterior'}),
            'promedio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej. 85.50'}),
            'razon_retiro': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Motivo de traslado o retiro'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar únicamente grados de Jornada Vespertina
        self.fields['grado_a_cursar'].queryset = CarreraCuota.objects.filter(
            jornada__icontains='Vespertina'
        ).order_by('orden', 'nivel_educativo', 'grado')
        self.fields['colegio_anterior'].required = False
        self.fields['promedio'].required = False
        self.fields['razon_retiro'].required = False

        if self.instance and self.instance.colegio_anterior:
            self.fields['es_nuevo_ingreso'].initial = True


class ContactoEmergenciaForm(forms.ModelForm):
    class Meta:
        model = ContactoEmergencia
        fields = ['nombre_completo', 'parentesco', 'celular']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. MARÍA ELENA LÓPEZ (Sin DPI)',
                'style': 'text-transform: uppercase;',
                'required': 'required',
            }),
            'parentesco': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. ABUELA, TÍO, ENCARGADO BUS...',
                'style': 'text-transform: uppercase;',
                'required': 'required',
            }),
            'celular': forms.TextInput(attrs={
                'class': 'form-control telefono-internacional',
                'placeholder': 'Número sin guiones',
                'maxlength': '20',
                'required': 'required',
            }),
        }


@login_required(login_url='/accounts/login/')
@user_passes_test(es_digitador_o_superior, login_url='/accounts/login/')
def buscar_dpi_staff_ajax(request, dpi):
    """
    Busca si el DPI o Pasaporte del responsable ya existe en la BD (ej. por otro hermano)
    y devuelve todos sus datos para autocompletar el formulario en la Sección B.
    """
    dpi_limpio = re.sub(r'[\s\-]+', '', dpi or '')
    responsable = Responsable.objects.filter(dpi=dpi_limpio).first()
    if responsable:
        return JsonResponse({
            'existe': True,
            'tipo_documento': getattr(responsable, 'tipo_documento', 'DPI'),
            'nombres': responsable.nombres or '',
            'apellidos': responsable.apellidos or '',
            'edad': responsable.edad or '',
            'estado_civil': responsable.estado_civil or 'Casado(a)',
            'direccion': responsable.direccion or '',
            'celular': responsable.celular or '',
            'tiene_whatsapp': getattr(responsable, 'tiene_whatsapp', True),
            'telefono_fijo': responsable.telefono_fijo or '',
            'profesion': responsable.profesion or '',
            'nacionalidad': responsable.nacionalidad or 'Guatemalteca',
            'religion': responsable.religion or '',
            'iglesia': responsable.iglesia or '',
            'correo_electronico': responsable.correo_electronico or '',
        })
    return JsonResponse({'existe': False})


# =========================================================================
# VISTAS DEL ROL: DIGITADOR
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_digitador_o_superior, login_url='/accounts/login/')
def panel_digitador(request):
    """Bandeja del Digitador con pestañas de Pendientes, Inscritos y Todos."""
    # Acción exclusiva del Supervisor: Generar tickets masivos a todos los que están SIN TICKET
    if request.method == 'POST' and request.POST.get('accion') == 'generar_tickets_faltantes':
        if request.user.is_superuser:
            sin_ticket_qs = Inscripcion.objects.filter(
                Q(ticket_generado__isnull=True) | Q(ticket_generado='')
            )
            total_generados = 0
            for insc in sin_ticket_qs:
                insc.ticket_generado = generar_codigo_ticket()
                insc.save(update_fields=['ticket_generado'])
                total_generados += 1
            messages.success(
                request,
                f'⚡ Se generaron y asignaron {total_generados} códigos de Ticket a los expedientes que no tenían.'
            )
        return redirect('panel_digitador')

    query = request.GET.get('q', '').strip()
    query_limpio = re.sub(r'[\s\-]+', '', query)
    filtro_estado = request.GET.get('estado', 'pendientes')

    if filtro_estado == 'inscritos':
        inscripciones_qs = Inscripcion.objects.filter(estado_solicitud='INSCRITO').select_related('estudiante', 'grado_a_cursar').order_by('-id')
    elif filtro_estado == 'todos':
        inscripciones_qs = Inscripcion.objects.all().select_related('estudiante', 'grado_a_cursar').order_by('-id')
    else:
        inscripciones_qs = Inscripcion.objects.exclude(estado_solicitud='INSCRITO').select_related('estudiante', 'grado_a_cursar').order_by('-id')

    if query:
        q_cond = (
            Q(ticket_generado__icontains=query) |
            Q(correlativo_contrato__icontains=query) |
            Q(estudiante__cui__icontains=query) |
            Q(estudiante__nombres__icontains=query) |
            Q(estudiante__apellidos__icontains=query)
        )
        if query_limpio and query_limpio != query:
            q_cond |= Q(estudiante__cui__icontains=query_limpio)

        inscripciones_filtradas = inscripciones_qs.filter(q_cond)
        if not inscripciones_filtradas.exists() and filtro_estado == 'pendientes':
            inscripciones_filtradas = Inscripcion.objects.filter(q_cond).select_related('estudiante', 'grado_a_cursar').order_by('-id')
            filtro_estado = 'todos'
        inscripciones_qs = inscripciones_filtradas

    total_pendientes = Inscripcion.objects.exclude(estado_solicitud='INSCRITO').count()
    total_inscritos = Inscripcion.objects.filter(estado_solicitud='INSCRITO').count()
    total_sin_ticket = Inscripcion.objects.filter(Q(ticket_generado__isnull=True) | Q(ticket_generado='')).count()

    context = {
        'inscripciones': inscripciones_qs,
        'query': query,
        'filtro_estado': filtro_estado,
        'total_pendientes': total_pendientes,
        'total_inscritos': total_inscritos,
        'total_sin_ticket': total_sin_ticket,
    }
    return render(request, 'portal_staff/panel_digitador.html', context)


@login_required(login_url='/accounts/login/')
@user_passes_test(es_digitador_o_superior, login_url='/accounts/login/')
def editar_expediente_digitador(request, inscripcion_id):
    """
    Vista de auditoría completa:
    Sección A (Alumno y Grado), Sección B (Responsables/Firmante) y Sección C (Emergencias).
    Registra automáticamente qué usuario editó y quién oficializó el contrato.
    """
    inscripcion = get_object_or_404(Inscripcion, id=inscripcion_id)
    estudiante = inscripcion.estudiante

    vinculos = EstudianteResponsable.objects.filter(
        estudiante=estudiante
    ).select_related('responsable').order_by('-es_contacto_principal', 'id')
    contactos_emergencia = ContactoEmergencia.objects.filter(estudiante=estudiante)

    config_grados = {str(c.id): getattr(c, 'config_ingreso', 'MANUAL') for c in CarreraCuota.objects.all()}

    editar_dpi = request.GET.get('editar_resp')
    nuevo_resp = request.GET.get('nuevo_resp')

    vinculo_a_editar = None
    responsable_a_editar = None

    if editar_dpi:
        vinculo_a_editar = vinculos.filter(responsable__dpi=editar_dpi).first()
        if vinculo_a_editar:
            responsable_a_editar = vinculo_a_editar.responsable
        else:
            responsable_a_editar = Responsable.objects.filter(dpi=editar_dpi).first()

    form_estudiante = EstudianteForm(instance=estudiante)
    form_inscripcion = InscripcionDigitadorForm(instance=inscripcion)
    form_responsable = ResponsableForm(
        instance=responsable_a_editar,
        initial={
            'parentesco_tipo': vinculo_a_editar.parentesco if vinculo_a_editar else 'Padre',
        }
    )
    form_emergencia = ContactoEmergenciaForm()

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # ACCIÓN A: GUARDAR O EDITAR UN RESPONSABLE LEGAL (CON DPI)
        if accion == 'guardar_responsable':
            dpi_raw = request.POST.get('dpi', '').strip()
            dpi_ingresado = re.sub(r'[\s\-]+', '', dpi_raw)
            instancia_resp = Responsable.objects.filter(dpi=dpi_ingresado).first()

            post_data = request.POST.copy()
            if dpi_ingresado:
                post_data['dpi'] = dpi_ingresado

            form_responsable = ResponsableForm(post_data, instance=instancia_resp)

            if form_responsable.is_valid():
                resp_obj = form_responsable.save(commit=False)
                for campo in ['nombres', 'apellidos', 'estado_civil', 'direccion', 'profesion', 'nacionalidad', 'religion', 'iglesia']:
                    valor = getattr(resp_obj, campo, None)
                    if valor and isinstance(valor, str):
                        setattr(resp_obj, campo, valor.strip().upper())
                resp_obj.save()

                parentesco_elegido = form_responsable.cleaned_data.get('parentesco_tipo', 'Encargado')
                marcar_principal = request.POST.get('es_contacto_principal') == 'on'

                if marcar_principal or not vinculos.exists():
                    EstudianteResponsable.objects.filter(estudiante=estudiante).update(es_contacto_principal=False)
                    marcar_principal = True

                EstudianteResponsable.objects.update_or_create(
                    estudiante=estudiante,
                    responsable=resp_obj,
                    defaults={
                        'parentesco': parentesco_elegido,
                        'es_contacto_principal': marcar_principal,
                    }
                )
                inscripcion.ultima_edicion_por = request.user
                inscripcion.save()

                messages.success(request, f'✅ Responsable {resp_obj.nombres} {resp_obj.apellidos} guardado correctamente.')
                return redirect(f"/digitador/editar/{inscripcion.id}/#seccion-responsables")
            else:
                messages.error(request, '⚠️ No se pudo guardar el responsable. Revise los campos marcados en la Sección B.')

        # ACCIÓN B: CAMBIAR QUIÉN FIRMA EL CONTRATO ESE DÍA
        elif accion == 'hacer_principal':
            vinculo_id = request.POST.get('vinculo_id')
            EstudianteResponsable.objects.filter(estudiante=estudiante).update(es_contacto_principal=False)
            EstudianteResponsable.objects.filter(id=vinculo_id, estudiante=estudiante).update(es_contacto_principal=True)
            inscripcion.ultima_edicion_por = request.user
            inscripcion.save()

            nuevo_firmante = EstudianteResponsable.objects.filter(id=vinculo_id).select_related('responsable').first()
            if nuevo_firmante:
                messages.success(
                    request,
                    f'✅ Ahora el firmante principal que saldrá impreso en el contrato es: {nuevo_firmante.responsable.nombres} {nuevo_firmante.responsable.apellidos} ({nuevo_firmante.parentesco}).'
                )
            return redirect(f"/digitador/editar/{inscripcion.id}/#seccion-responsables")

        # ACCIÓN C: DESVINCULAR UN RESPONSABLE DEL ESTUDIANTE
        elif accion == 'desvincular_responsable':
            vinculo_id = request.POST.get('vinculo_id')
            EstudianteResponsable.objects.filter(id=vinculo_id, estudiante=estudiante).delete()
            inscripcion.ultima_edicion_por = request.user
            inscripcion.save()
            messages.warning(request, 'Se desvinculó al responsable de este estudiante.')
            return redirect(f"/digitador/editar/{inscripcion.id}/#seccion-responsables")

        # ACCIÓN D: AGREGAR CONTACTO DE EMERGENCIA (SIN DPI - ILIMITADOS)
        elif accion == 'agregar_emergencia':
            form_emergencia = ContactoEmergenciaForm(request.POST)
            if form_emergencia.is_valid():
                emerg_obj = form_emergencia.save(commit=False)
                emerg_obj.estudiante = estudiante
                emerg_obj.nombre_completo = emerg_obj.nombre_completo.strip().upper()
                emerg_obj.parentesco = emerg_obj.parentesco.strip().upper()
                emerg_obj.celular = emerg_obj.celular.strip()
                emerg_obj.save()

                inscripcion.ultima_edicion_por = request.user
                inscripcion.save()

                messages.success(request, f'✅ Contacto de emergencia "{emerg_obj.nombre_completo}" agregado.')
                return redirect(f"/digitador/editar/{inscripcion.id}/#seccion-emergencias")
            else:
                messages.error(request, 'Error al agregar contacto de emergencia.')

        # ACCIÓN E: ELIMINAR CONTACTO DE EMERGENCIA
        elif accion == 'eliminar_emergencia':
            emergencia_id = request.POST.get('emergencia_id')
            ContactoEmergencia.objects.filter(id=emergencia_id, estudiante=estudiante).delete()
            inscripcion.ultima_edicion_por = request.user
            inscripcion.save()
            messages.warning(request, 'Contacto de emergencia eliminado.')
            return redirect(f"/digitador/editar/{inscripcion.id}/#seccion-emergencias")

        # ACCIÓN F: GUARDAR DATOS DEL ALUMNO U OFICIALIZAR E IR DIRECTO AL CONTRATO PDF
        elif accion in ['actualizar', 'oficializar']:
            form_estudiante = EstudianteForm(request.POST, instance=estudiante)
            form_inscripcion = InscripcionDigitadorForm(request.POST, instance=inscripcion)

            if form_estudiante.is_valid() and form_inscripcion.is_valid():
                est_obj = form_estudiante.save(commit=False)

                if not form_estudiante.cleaned_data.get('tiene_enfermedad'):
                    est_obj.enfermedades_padece = ''
                if not form_estudiante.cleaned_data.get('impedimento_fisico'):
                    est_obj.detalle_impedimento = ''
                if est_obj.vive_con and 'Otro' not in est_obj.vive_con:
                    est_obj.vive_con_otro = ''
                if est_obj.depende_de and 'Otro' not in est_obj.depende_de:
                    est_obj.depende_de_otro = ''

                for campo in ['nombres', 'apellidos', 'enfermedades_padece', 'detalle_impedimento', 'vive_con_otro', 'depende_de_otro']:
                    valor = getattr(est_obj, campo, None)
                    if valor and isinstance(valor, str):
                        setattr(est_obj, campo, valor.strip().upper())
                est_obj.save()

                insc_obj = form_inscripcion.save(commit=False)
                insc_obj.ultima_edicion_por = request.user

                grado = insc_obj.grado_a_cursar
                comportamiento_grado = getattr(grado, 'config_ingreso', 'MANUAL') if grado else 'MANUAL'
                es_nuevo = form_inscripcion.cleaned_data.get('es_nuevo_ingreso', False)

                if comportamiento_grado == 'OCULTO' or (comportamiento_grado == 'MANUAL' and not es_nuevo):
                    insc_obj.colegio_anterior = ''
                    insc_obj.promedio = None
                    insc_obj.razon_retiro = ''
                else:
                    if insc_obj.colegio_anterior:
                        insc_obj.colegio_anterior = insc_obj.colegio_anterior.strip().upper()
                    if insc_obj.razon_retiro:
                        insc_obj.razon_retiro = insc_obj.razon_retiro.strip().upper()

                if accion == 'oficializar':
                    if not grado:
                        messages.error(request, '⚠️ No puede oficializar: Falta seleccionar el GRADO A CURSAR en la Sección A.')
                        return redirect('editar_expediente', inscripcion_id=inscripcion.id)

                    if comportamiento_grado == 'OBLIGATORIO' or (comportamiento_grado == 'MANUAL' and es_nuevo):
                        if not insc_obj.colegio_anterior:
                            messages.error(request, '⚠️ Como es estudiante de Primer Ingreso, debe indicar el Colegio Anterior en la Sección A.')
                            return redirect('editar_expediente', inscripcion_id=inscripcion.id)

                    resp_principal = EstudianteResponsable.objects.filter(
                        estudiante=estudiante, es_contacto_principal=True
                    ).select_related('responsable').first()
                    if not resp_principal:
                        messages.error(request, '⚠️ No puede oficializar: Debe registrar al menos un RESPONSABLE LEGAL (Con DPI) y elegir quién firma el contrato en la Sección B.')
                        return redirect('editar_expediente', inscripcion_id=inscripcion.id)

                    r = resp_principal.responsable
                    campos_faltantes = []
                    if not r.dpi:
                        campos_faltantes.append('DPI')
                    if not r.nombres or not r.apellidos:
                        campos_faltantes.append('Nombres/Apellidos')
                    if not r.direccion:
                        campos_faltantes.append('Dirección de residencia')
                    if not r.celular:
                        campos_faltantes.append('Celular')
                    if not r.estado_civil:
                        campos_faltantes.append('Estado Civil')
                    if not r.profesion:
                        campos_faltantes.append('Profesión u Oficio')

                    if campos_faltantes:
                        messages.error(
                            request,
                            f'⚠️ El firmante seleccionado ({r.nombres} {r.apellidos}) tiene datos incompletos para el contrato: {", ".join(campos_faltantes)}. Complételos abajo.'
                        )
                        return redirect(f"/digitador/editar/{inscripcion.id}/?editar_resp={r.dpi}#form-edicion-responsable")

                    # Transacción atómica para evitar duplicidad de correlativo o descuento doble de cupo por doble clic
                    with transaction.atomic():
                        insc_bloqueada = Inscripcion.objects.select_for_update().get(id=inscripcion.id)
                        grado_bloqueado = CarreraCuota.objects.select_for_update().get(id=grado.id)
                        es_dir = es_direccion(request.user)

                        if insc_bloqueada.estado_solicitud != 'INSCRITO':
                            if grado_bloqueado.cupos_ocupados >= grado_bloqueado.cupo_maximo and not es_dir:
                                messages.error(request, f'⚠️ ¡Cupo lleno en {grado_bloqueado}! Solicite autorización a Dirección para inscribirlo.')
                                return redirect('editar_expediente', inscripcion_id=inscripcion.id)

                            grado_bloqueado.cupos_ocupados += 1
                            grado_bloqueado.save(update_fields=['cupos_ocupados'])

                        if not insc_bloqueada.correlativo_contrato:
                            config = ConfiguracionAnual.objects.select_for_update().filter(
                                anio_ciclo=grado_bloqueado.ciclo.anio_ciclo
                            ).first() or ConfiguracionAnual.objects.select_for_update().last()
                            if config:
                                insc_obj.correlativo_contrato = construir_correlativo_oficial(config, grado_bloqueado)
                                config.correlativo_actual += 1
                                config.save(update_fields=['correlativo_actual'])
                        else:
                            insc_obj.correlativo_contrato = insc_bloqueada.correlativo_contrato

                        if not insc_bloqueada.inscrito_por:
                            insc_obj.inscrito_por = request.user
                        else:
                            insc_obj.inscrito_por = insc_bloqueada.inscrito_por

                        if not insc_bloqueada.fecha_oficializacion:
                            insc_obj.fecha_oficializacion = timezone.now()
                        else:
                            insc_obj.fecha_oficializacion = insc_bloqueada.fecha_oficializacion

                        insc_obj.estado_solicitud = 'INSCRITO'
                        insc_obj.save()

                    return redirect(f"{reverse('descargar_contrato_pdf', args=[inscripcion.id])}?forzar_pdf=1")

                else:
                    insc_obj.save()
                    messages.success(request, '✅ Datos del estudiante y grado actualizados correctamente.')
                    return redirect('editar_expediente', inscripcion_id=inscripcion.id)
            else:
                messages.error(request, '⚠️ Por favor revise los campos obligatorios del Estudiante en la Sección A.')

    firmante_actual = vinculos.filter(es_contacto_principal=True).first()

    context = {
        'inscripcion': inscripcion,
        'estudiante': estudiante,
        'vinculos': vinculos,
        'firmante_actual': firmante_actual,
        'contactos_emergencia': contactos_emergencia,
        'vinculo_a_editar': vinculo_a_editar,
        'responsable_a_editar': responsable_a_editar,
        'mostrar_form_responsable': bool(editar_dpi or nuevo_resp or not vinculos.exists() or form_responsable.errors),
        'form_estudiante': form_estudiante,
        'form_inscripcion': form_inscripcion,
        'form_responsable': form_responsable,
        'form_emergencia': form_emergencia,
        'config_grados_json': json.dumps(config_grados),
    }
    return render(request, 'portal_staff/panel_digitador_edicion.html', context)


# =========================================================================
# VISTAS DEL ROL: SECRETARÍA GENERAL (POST-INSCRIPCIÓN, NÓMINAS Y ANULACIONES)
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_secretaria_o_superior, login_url='/accounts/login/')
def panel_secretaria(request):
    """Centro de Control de Secretaría General."""
    if request.method == 'POST':
        accion = request.POST.get('accion')
        inscripcion_id = request.POST.get('inscripcion_id')
        inscripcion = get_object_or_404(Inscripcion, id=inscripcion_id)
        estudiante = inscripcion.estudiante

        if accion == 'toggle_expediente_fisico':
            inscripcion.expediente_fisico_completo = not inscripcion.expediente_fisico_completo
            inscripcion.ultima_edicion_por = request.user
            inscripcion.save(update_fields=['expediente_fisico_completo', 'ultima_edicion_por'])

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                fisicos_ok = Inscripcion.objects.filter(estado_solicitud='INSCRITO', expediente_fisico_completo=True).count()
                fisicos_pend = Inscripcion.objects.filter(estado_solicitud='INSCRITO', expediente_fisico_completo=False).count()
                return JsonResponse({
                    'ok': True,
                    'completo': inscripcion.expediente_fisico_completo,
                    'fisicos_ok': fisicos_ok,
                    'fisicos_pend': fisicos_pend,
                })

            estado_txt = "COMPLETADO ✅" if inscripcion.expediente_fisico_completo else "PENDIENTE 📁"
            messages.success(
                request,
                f'📁 Expediente físico de {estudiante.nombres} {estudiante.apellidos} marcado como: {estado_txt}'
            )
            return redirect(request.META.get('HTTP_REFERER', 'panel_secretaria'))

        elif accion == 'anular_contrato':
            if inscripcion.estado_solicitud == 'INSCRITO':
                grado_actual = inscripcion.grado_a_cursar
                if grado_actual and grado_actual.cupos_ocupados > 0:
                    grado_actual.cupos_ocupados -= 1
                    grado_actual.save()

                correlativo_anterior = inscripcion.correlativo_contrato
                inscripcion.estado_solicitud = 'PREINSCRITO'
                inscripcion.ultima_edicion_por = request.user
                inscripcion.save()
                messages.warning(
                    request,
                    f'⚠️ Se anuló la inscripción oficial de {estudiante.nombres} {estudiante.apellidos} (Contrato {correlativo_anterior}). Se liberó 1 cupo en {grado_actual.grado} y el expediente volvió a estado Preinscrito.'
                )
            return redirect('panel_secretaria')

        elif accion == 'cambiar_grado':
            nuevo_grado_id = request.POST.get('nuevo_grado_id')
            if nuevo_grado_id:
                nuevo_grado = get_object_or_404(CarreraCuota, id=nuevo_grado_id)
                grado_viejo = inscripcion.grado_a_cursar

                if grado_viejo != nuevo_grado:
                    if inscripcion.estado_solicitud == 'INSCRITO':
                        if nuevo_grado.cupos_ocupados >= nuevo_grado.cupo_maximo and not es_direccion(request.user):
                            messages.error(
                                request,
                                f'⚠️ No se pudo trasladar a {nuevo_grado.grado} porque el cupo está lleno ({nuevo_grado.cupos_ocupados}/{nuevo_grado.cupo_maximo}).'
                            )
                            return redirect('panel_secretaria')

                        if grado_viejo and grado_viejo.cupos_ocupados > 0:
                            grado_viejo.cupos_ocupados -= 1
                            grado_viejo.save()

                        nuevo_grado.cupos_ocupados += 1
                        nuevo_grado.save()

                    inscripcion.grado_a_cursar = nuevo_grado
                    inscripcion.ultima_edicion_por = request.user
                    inscripcion.save()
                    messages.success(
                        request,
                        f'✅ {estudiante.nombres} {estudiante.apellidos} fue trasladado exitosamente a {nuevo_grado.grado} {nuevo_grado.orientacion or ""}.'
                    )
            return redirect('panel_secretaria')

        elif accion == 'eliminar_expediente':
            if inscripcion.estado_solicitud == 'INSCRITO' and inscripcion.grado_a_cursar:
                grado_actual = inscripcion.grado_a_cursar
                if grado_actual.cupos_ocupados > 0:
                    grado_actual.cupos_ocupados -= 1
                    grado_actual.save()
            nombre_borrado = f"{estudiante.nombres} {estudiante.apellidos} (CUI: {estudiante.cui})"
            inscripcion.delete()
            messages.error(request, f'🗑️ Se eliminó el registro de inscripción de {nombre_borrado}.')
            return redirect('panel_secretaria')

    query = request.GET.get('q', '').strip()
    query_limpio = re.sub(r'[\s\-]+', '', query)
    grado_filtro = request.GET.get('grado', '').strip()
    estado_filtro = request.GET.get('estado', 'INSCRITO').strip()
    fisico_filtro = request.GET.get('fisico', '').strip()

    inscripciones_qs = Inscripcion.objects.select_related('estudiante', 'grado_a_cursar').order_by('-id')

    if estado_filtro == 'PENDIENTES_COLA':
        inscripciones_qs = inscripciones_qs.exclude(estado_solicitud='INSCRITO')
    elif estado_filtro and estado_filtro != 'TODOS':
        inscripciones_qs = inscripciones_qs.filter(estado_solicitud=estado_filtro)

    if grado_filtro:
        inscripciones_qs = inscripciones_qs.filter(grado_a_cursar_id=grado_filtro)

    if fisico_filtro == 'COMPLETO':
        inscripciones_qs = inscripciones_qs.filter(expediente_fisico_completo=True)
    elif fisico_filtro == 'PENDIENTE':
        inscripciones_qs = inscripciones_qs.filter(expediente_fisico_completo=False)

    if query:
        q_cond = (
            Q(correlativo_contrato__icontains=query) |
            Q(ticket_generado__icontains=query) |
            Q(estudiante__cui__icontains=query) |
            Q(estudiante__nombres__icontains=query) |
            Q(estudiante__apellidos__icontains=query)
        )
        if query_limpio and query_limpio != query:
            q_cond |= Q(estudiante__cui__icontains=query_limpio)
        inscripciones_qs = inscripciones_qs.filter(q_cond)

    listado_expedientes = []
    for insc in inscripciones_qs:
        vinculo_prin = EstudianteResponsable.objects.filter(
            estudiante=insc.estudiante
        ).select_related('responsable').order_by('-es_contacto_principal', 'id').first()
        listado_expedientes.append({
            'inscripcion': insc,
            'estudiante': insc.estudiante,
            'vinculo': vinculo_prin,
            'responsable': vinculo_prin.responsable if vinculo_prin else None,
        })

    grados_disponibles = CarreraCuota.objects.filter(
        jornada__icontains='Vespertina'
    ).order_by('orden', 'nivel_educativo', 'grado')

    total_inscritos = Inscripcion.objects.filter(estado_solicitud='INSCRITO').count()
    total_fisico_ok = Inscripcion.objects.filter(estado_solicitud='INSCRITO', expediente_fisico_completo=True).count()
    total_fisico_pendiente = Inscripcion.objects.filter(estado_solicitud='INSCRITO', expediente_fisico_completo=False).count()
    total_preinscritos = Inscripcion.objects.filter(estado_solicitud='PREINSCRITO').count()
    total_borradores = Inscripcion.objects.filter(estado_solicitud='BORRADOR').count()
    total_en_cola = total_preinscritos + total_borradores

    context = {
        'listado_expedientes': listado_expedientes,
        'grados_disponibles': grados_disponibles,
        'query': query,
        'grado_filtro': grado_filtro,
        'estado_filtro': estado_filtro,
        'fisico_filtro': fisico_filtro,
        'total_inscritos': total_inscritos,
        'total_fisico_ok': total_fisico_ok,
        'total_fisico_pendiente': total_fisico_pendiente,
        'total_preinscritos': total_preinscritos,
        'total_borradores': total_borradores,
        'total_en_cola': total_en_cola,
    }
    return render(request, 'portal_staff/panel_secretaria.html', context)


@login_required(login_url='/accounts/login/')
@user_passes_test(es_superusuario_exclusivo, login_url='/accounts/login/')
def exportar_matricula_csv(request):
    """Exporta a Excel (CSV con BOM UTF-8) la nómina de estudiantes."""
    grado_filtro = request.GET.get('grado', '').strip()
    estado_filtro = request.GET.get('estado', 'INSCRITO').strip()
    fisico_filtro = request.GET.get('fisico', '').strip()
    query = request.GET.get('q', '').strip()

    qs = Inscripcion.objects.select_related('estudiante', 'grado_a_cursar').order_by(
        'grado_a_cursar__orden', 'estudiante__apellidos', 'estudiante__nombres'
    )

    if estado_filtro and estado_filtro != 'TODOS':
        qs = qs.filter(estado_solicitud=estado_filtro)
    if grado_filtro:
        qs = qs.filter(grado_a_cursar_id=grado_filtro)
    if fisico_filtro == 'COMPLETO':
        qs = qs.filter(expediente_fisico_completo=True)
    elif fisico_filtro == 'PENDIENTE':
        qs = qs.filter(expediente_fisico_completo=False)
    if query:
        qs = qs.filter(
            Q(correlativo_contrato__icontains=query) |
            Q(estudiante__cui__icontains=query) |
            Q(estudiante__nombres__icontains=query) |
            Q(estudiante__apellidos__icontains=query)
        )

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="Nomina_Colegio_Amigos_2027_{estado_filtro}.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'CORRELATIVO CONTRATO',
        'ESTADO',
        'EXPEDIENTE FISICO COMPLETO',
        'CUI ESTUDIANTE',
        'APELLIDOS ESTUDIANTE',
        'NOMBRES ESTUDIANTE',
        'GENERO',
        'FECHA NACIMIENTO',
        'EDAD',
        'GRADO A CURSAR',
        'CARRERA / ORIENTACION',
        'JORNADA',
        'TELEFONO ESTUDIANTE',
        'TIPO SANGRE',
        'ENFERMEDADES / ALERGIAS',
        'FIRMANTE PRINCIPAL',
        'PARENTESCO',
        'DPI FIRMANTE',
        'CELULAR FIRMANTE',
        'DIRECCION RESIDENCIA',
        'CONTACTOS EMERGENCIA',
    ])

    for insc in qs:
        est = insc.estudiante
        grado = insc.grado_a_cursar
        vinculo = EstudianteResponsable.objects.filter(
            estudiante=est
        ).select_related('responsable').order_by('-es_contacto_principal', 'id').first()
        resp = vinculo.responsable if vinculo else None

        emergencias = ContactoEmergencia.objects.filter(estudiante=est)
        emerg_str = " | ".join([f"{e.nombre_completo} ({e.parentesco}: {e.celular})" for e in emergencias])

        writer.writerow([
            insc.correlativo_contrato or 'SIN CORRELATIVO',
            insc.estado_solicitud,
            'SI (COMPLETO)' if insc.expediente_fisico_completo else 'PENDIENTE',
            f"'{est.cui}",
            est.apellidos,
            est.nombres,
            est.genero or '',
            est.fecha_nacimiento.strftime('%d/%m/%Y') if est.fecha_nacimiento else '',
            est.edad or '',
            grado.grado if grado else 'SIN ASIGNAR',
            grado.orientacion if (grado and grado.orientacion) else 'N/A',
            grado.jornada if grado else '',
            est.telefono or '',
            est.tipo_sangre or '',
            est.enfermedades_padece or 'NINGUNA',
            f"{resp.nombres} {resp.apellidos}" if resp else 'SIN REGISTRAR',
            vinculo.parentesco if vinculo else '',
            f"'{resp.dpi}" if resp else '',
            resp.celular if resp else '',
            resp.direccion if resp else '',
            emerg_str,
        ])

    return response


# =========================================================================
# VISTA DEL PORTAL DE DIRECCIÓN (DASHBOARD DE CUPOS)
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_direccion, login_url='/accounts/login/')
def panel_direccion(request):
    """Dashboard Ejecutivo para Dirección: KPIs globales y ampliación de cupos con confirmación."""
    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'actualizar_cupo':
            carrera_id = request.POST.get('carrera_id')
            nuevo_cupo_str = request.POST.get('nuevo_cupo', '').strip()
            carrera = get_object_or_404(CarreraCuota, id=carrera_id)

            if nuevo_cupo_str.isdigit():
                nuevo_cupo = int(nuevo_cupo_str)
                inscritos_reales = Inscripcion.objects.filter(
                    grado_a_cursar=carrera,
                    estado_solicitud='INSCRITO'
                ).count()

                if nuevo_cupo < inscritos_reales:
                    messages.error(
                        request,
                        f'⚠️ No puede reducir el cupo de "{carrera.grado}" a {nuevo_cupo} porque ya existen {inscritos_reales} alumnos oficialmente inscritos.'
                    )
                else:
                    cupo_anterior = carrera.cupo_maximo
                    carrera.cupo_maximo = nuevo_cupo
                    carrera.cupos_ocupados = inscritos_reales
                    carrera.save()
                    messages.success(
                        request,
                        f'✅ Cupo actualizado en "{carrera.grado} ({carrera.jornada})": pasó de {cupo_anterior} a {nuevo_cupo} espacios.'
                    )
            else:
                messages.error(request, '⚠️ Ingrese un número entero válido para el cupo.')

            return redirect('panel_direccion')

        elif accion == 'sincronizar_cupos':
            for c in CarreraCuota.objects.all():
                c.cupos_ocupados = Inscripcion.objects.filter(
                    grado_a_cursar=c,
                    estado_solicitud='INSCRITO'
                ).count()
                c.save()
            messages.info(request, '🔄 Todos los contadores de cupos fueron auditados y sincronizados con los contratos inscritos.')
            return redirect('panel_direccion')

    carreras = CarreraCuota.objects.select_related('ciclo').all()
    cuotas_tabla = list(CuotaMineducContrato.objects.all())

    total_cupo_colegio = 0
    total_inscritos_colegio = 0
    total_en_proceso_colegio = 0
    grados_llenos = 0

    datos_grados = []

    for c in carreras:
        # Buscar su tarifa correspondiente directamente en la tabla CuotaMineducContrato
        texto_grado = _normalizar_texto(f"{c.nivel_educativo} {c.grado} {c.orientacion or ''}")
        cuota_match = None

        for ct in cuotas_tabla:
            nivel_ct = _normalizar_texto(ct.nivel_educacion)
            if ('computacion' in nivel_ct or 'bachillerato' in nivel_ct) and ('computacion' in texto_grado or 'bachillerato' in texto_grado):
                cuota_match = ct
                break
            elif ('perito' in nivel_ct or 'administracion' in nivel_ct or 'pae' in nivel_ct) and ('perito' in texto_grado or 'administracion' in texto_grado or 'pae' in texto_grado):
                cuota_match = ct
                break
            elif 'basico' in nivel_ct and 'basico' in texto_grado:
                cuota_match = ct
                break
            elif 'preprimaria' in nivel_ct and 'preprimaria' in texto_grado:
                cuota_match = ct
                break
            elif 'primaria' in nivel_ct and 'primaria' in texto_grado and 'preprimaria' not in texto_grado:
                cuota_match = ct
                break

        # Sincronizar los montos reales (MENSUALIDAD A COBRAR COLEGIO e INSCRIPCIÓN A COBRAR COLEGIO)
        if cuota_match:
            if c.cuota_inscripcion != cuota_match.inscripcion_colegio or c.cuota_mensual != cuota_match.mensualidad_colegio:
                c.cuota_inscripcion = cuota_match.inscripcion_colegio
                c.cuota_mensual = cuota_match.mensualidad_colegio
                c.save(update_fields=['cuota_inscripcion', 'cuota_mensual'])

        inscritos = Inscripcion.objects.filter(grado_a_cursar=c, estado_solicitud='INSCRITO').count()
        preinscritos = Inscripcion.objects.filter(grado_a_cursar=c, estado_solicitud='PREINSCRITO').count()
        borradores = Inscripcion.objects.filter(grado_a_cursar=c, estado_solicitud='BORRADOR').count()

        if c.cupos_ocupados != inscritos:
            c.cupos_ocupados = inscritos
            c.save(update_fields=['cupos_ocupados'])

        disponibles = max(0, c.cupo_maximo - inscritos)
        porcentaje = round((inscritos / c.cupo_maximo) * 100) if c.cupo_maximo > 0 else 100
        porcentaje_barra = min(100, porcentaje)

        if inscritos >= c.cupo_maximo and c.cupo_maximo > 0:
            grados_llenos += 1
            color_estado = 'danger'
            etiqueta_estado = 'CUPO LLENO'
        elif porcentaje >= 80:
            color_estado = 'warning'
            etiqueta_estado = 'CASI LLENO'
        else:
            color_estado = 'success'
            etiqueta_estado = 'DISPONIBLE'

        total_cupo_colegio += c.cupo_maximo
        total_inscritos_colegio += inscritos
        total_en_proceso_colegio += (preinscritos + borradores)

        datos_grados.append({
            'instancia': c,
            'inscritos': inscritos,
            'preinscritos': preinscritos,
            'borradores': borradores,
            'en_proceso': preinscritos + borradores,
            'disponibles': disponibles,
            'porcentaje': porcentaje,
            'porcentaje_barra': porcentaje_barra,
            'color_estado': color_estado,
            'etiqueta_estado': etiqueta_estado,
        })

    sin_grado = Inscripcion.objects.filter(grado_a_cursar__isnull=True).exclude(estado_solicitud='INSCRITO').count()
    total_en_proceso_colegio += sin_grado

    total_disponibles_colegio = max(0, total_cupo_colegio - total_inscritos_colegio)
    porcentaje_global = round((total_inscritos_colegio / total_cupo_colegio) * 100) if total_cupo_colegio > 0 else 0

    context = {
        'datos_grados': datos_grados,
        'total_cupo_colegio': total_cupo_colegio,
        'total_inscritos_colegio': total_inscritos_colegio,
        'total_disponibles_colegio': total_disponibles_colegio,
        'total_en_proceso_colegio': total_en_proceso_colegio,
        'sin_grado': sin_grado,
        'grados_llenos': grados_llenos,
        'porcentaje_global': porcentaje_global,
    }
    return render(request, 'portal_staff/panel_direccion.html', context)


# =========================================================================
# GENERACIÓN DEL CONTRATO DIACO 2027 Y FICHA INFORMATIVA (TAMAÑO OFICIO)
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_digitador_o_superior, login_url='/accounts/login/')
def descargar_contrato_pdf(request, inscripcion_id):
    """
    Genera el Contrato de Adhesión DIACO 2027 y la Ficha Informativa en tamaño Oficio.
    CANDADO ESTRICTO: Bloqueado para alumnos en BORRADOR o PREINSCRITO para no alterar correlativos.
    """
    inscripcion = get_object_or_404(Inscripcion, id=inscripcion_id)
    estudiante = inscripcion.estudiante
    grado = inscripcion.grado_a_cursar

    # 1. CANDADO DE SEGURIDAD: Prohibir abrir o generar el contrato si aún no está INSCRITO
    if inscripcion.estado_solicitud != 'INSCRITO':
        messages.warning(
            request,
            f'🔒 El Contrato y la Ficha Informativa de {estudiante.nombres} {estudiante.apellidos} están bloqueados hasta que confirme y oficialice la inscripción.'
        )
        return redirect('editar_expediente', inscripcion_id=inscripcion.id)

    todos_los_vinculos = EstudianteResponsable.objects.filter(
        estudiante=estudiante
    ).select_related('responsable').order_by('-es_contacto_principal', 'id')

    vinculo_principal = todos_los_vinculos.filter(es_contacto_principal=True).first() or todos_los_vinculos.first()

    if not vinculo_principal or not grado:
        messages.error(request, '⚠️ Antes de generar el contrato debe asignar el Grado a Cursar y un Responsable Firmante Principal.')
        return redirect('editar_expediente', inscripcion_id=inscripcion.id)

    responsable = vinculo_principal.responsable
    contactos_emergencia = ContactoEmergencia.objects.filter(estudiante=estudiante)
    config = ConfiguracionAnual.objects.filter(anio_ciclo=grado.ciclo.anio_ciclo).first() or ConfiguracionAnual.objects.last()

    # Solo asigna correlativo si el alumno YA ESTÁ INSCRITO y por alguna razón no lo tenía
    if not inscripcion.correlativo_contrato and config:
        with transaction.atomic():
            config_lock = ConfiguracionAnual.objects.select_for_update().get(id=config.id)
            inscripcion.correlativo_contrato = construir_correlativo_oficial(config_lock, grado)
            config_lock.correlativo_actual += 1
            config_lock.save(update_fields=['correlativo_actual'])
            inscripcion.save(update_fields=['correlativo_contrato'])

    correlativo = inscripcion.correlativo_contrato

    # 2. Poblar o actualizar las 5 filas oficiales del Contrato 2027 exclusivamente en CuotaMineducContrato
    if config:
        datos_contrato_2027 = [
            ('MATUTINA', 1, 'Pre-primaria', '550.00', '385.00', '608.35', '395.43'),
            ('MATUTINA', 2, 'Primaria', '550.00', '385.00', '608.35', '395.43'),
            ('VESPERTINA', 3, 'Básico', '630.00', '480.00', '760.44', '532.31'),
            ('VESPERTINA', 4, 'Perito en Administración de Empresas', '700.00', '525.00', '912.52', '577.93'),
            ('VESPERTINA', 5, 'Bachillerato en Ciencias y Letras con Orientación en Computación', '750.00', '650.00', '912.52', '730.02'),
        ]
        if not CuotaMineducContrato.objects.filter(ciclo=config).exists():
            for jorn, ord_num, niv, insc_col, mens_col, insc_min, mens_min in datos_contrato_2027:
                CuotaMineducContrato.objects.create(
                    ciclo=config,
                    jornada=jorn,
                    orden=ord_num,
                    nivel_educacion=niv,
                    inscripcion_colegio=insc_col,
                    mensualidad_colegio=mens_col,
                    inscripcion=insc_min,
                    colegiatura_mensual=mens_min,
                )
        else:
            for jorn, ord_num, niv, insc_col, mens_col, insc_min, mens_min in datos_contrato_2027:
                CuotaMineducContrato.objects.filter(
                    ciclo=config, orden=ord_num, inscripcion_colegio=0
                ).update(
                    nivel_educacion=niv,
                    inscripcion_colegio=insc_col,
                    mensualidad_colegio=mens_col,
                    inscripcion=insc_min,
                    colegiatura_mensual=mens_min,
                )

    cuotas_mineduc_todas = CuotaMineducContrato.objects.filter(ciclo=config).order_by('orden', 'id') if config else []

    # 3. Construir la lista para la Tabla 1 de la Cláusula Sexta (Cobro Colegio de todos los niveles)
    cuotas_colegio_todos = []
    for item in cuotas_mineduc_todas:
        etiqueta_upper = item.nivel_educacion.replace('-', '').strip().upper()
        insc_c = f"{int(item.inscripcion_colegio)}" if item.inscripcion_colegio == int(item.inscripcion_colegio) else f"{item.inscripcion_colegio:.2f}"
        mens_c = f"{int(item.mensualidad_colegio)}" if item.mensualidad_colegio == int(item.mensualidad_colegio) else f"{item.mensualidad_colegio:.2f}"
        cuotas_colegio_todos.append({
            'etiqueta': etiqueta_upper,
            'inscripcion': insc_c,
            'mensualidad': mens_c,
        })

    # 4. Convertir la imagen PNG de la firma a Base64 directo desde el disco
    firma_base64 = None
    if config and config.firma_representante_legal:
        try:
            ruta_firma = config.firma_representante_legal.path
            if os.path.exists(ruta_firma):
                with open(ruta_firma, 'rb') as img_f:
                    encoded = base64.b64encode(img_f.read()).decode('utf-8')
                    firma_base64 = f"data:image/png;base64,{encoded}"
        except Exception:
            firma_base64 = None

    if not firma_base64:
        ruta_estatica = os.path.join(settings.BASE_DIR, 'static_global', 'portal_staff', 'img', 'firma_representante.png')
        if os.path.exists(ruta_estatica):
            with open(ruta_estatica, 'rb') as img_f:
                encoded = base64.b64encode(img_f.read()).decode('utf-8')
                firma_base64 = f"data:image/png;base64,{encoded}"

    # 5. Fecha en español usando Zona Horaria Local de Guatemala
    meses_es = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
        7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    anios_sufijo = {
        2026: 'veintiséis',
        2027: 'veintisiete',
        2028: 'veintiocho',
    }
    hoy = timezone.localdate()

    if getattr(responsable, 'tipo_documento', 'DPI') == 'Pasaporte':
        frase_documento = "Pasaporte número"
    else:
        frase_documento = "Documento Personal de Identificación -DPI- con Código Único de Identificación -CUI- número"

    sigla_jornada_ficha = 'JM' if 'MATUTINA' in (grado.jornada or '').upper() else 'JV'

    mora_val = config.monto_mora if config else 20
    mora_str = f"{int(mora_val)}" if mora_val == int(mora_val) else f"{mora_val:.2f}"

    context = {
        'inscripcion': inscripcion,
        'estudiante': estudiante,
        'grado': grado,
        'responsable': responsable,
        'vinculo_principal': vinculo_principal,
        'todos_los_vinculos': todos_los_vinculos,
        'contactos_emergencia': contactos_emergencia,
        'config': config,
        'correlativo': correlativo,
        'sigla_jornada_ficha': sigla_jornada_ficha,
        'cuotas_colegio_todos': cuotas_colegio_todos,
        'cuotas_mineduc_todas': cuotas_mineduc_todas,
        'mora_str': mora_str,
        'firma_base64': firma_base64,
        'fecha_dia': hoy.day,
        'fecha_mes': meses_es.get(hoy.month, ''),
        'fecha_anio': hoy.year,
        'fecha_anio_sufijo': anios_sufijo.get(hoy.year, str(hoy.year)),
        'frase_documento': frase_documento,
        'url_base': f"{request.scheme}://{request.get_host()}",
        'modo_weasyprint': True,  # Siempre activo para no mostrar nunca la barra HTML intermedia
    }

    try:
        from weasyprint import HTML
        html_string = render_to_string('portal_staff/contrato_pdf.html', context, request=request)
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Contrato_{correlativo}_{estudiante.cui}.pdf"'
        return response
    except Exception:
        # En Windows local (si no está instalado GTK/WeasyPrint), abre directo el diálogo de impresión y oculta la barra
        return render(request, 'portal_staff/contrato_pdf.html', context)


# =========================================================================
# VISTA EXCLUSIVA DEL SUPERVISOR (PRODUCTIVIDAD DE DIGITADORES Y SECRETARÍA)
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_superusuario_exclusivo, login_url='/accounts/login/')
def panel_supervisor(request):
    """
    Dashboard Privado del Supervisor:
    Muestra exclusivamente a usuarios de los grupos 'Digitadores' y 'Secretaría General'
    (Excluye al Superusuario/Supervisor y a los Auxiliares).
    """
    hoy = timezone.localdate()
    digitador_id = request.GET.get('digitador', '').strip()
    fecha_filtro = request.GET.get('fecha', '').strip()
    query = request.GET.get('q', '').strip()

    # Filtrar únicamente Digitadores y Secretaría General, excluyendo Superusuarios
    usuarios_staff = User.objects.filter(
        is_superuser=False
    ).filter(
        Q(groups__name__icontains='digitador') |
        Q(groups__name__icontains='secretar')
    ).distinct()

    total_contratos_global = Inscripcion.objects.filter(estado_solicitud='INSCRITO').count()
    contratos_hoy_global = Inscripcion.objects.filter(
        estado_solicitud='INSCRITO',
        fecha_oficializacion__date=hoy
    ).count()
    sin_atribuir = Inscripcion.objects.filter(
        estado_solicitud='INSCRITO',
        inscrito_por__isnull=True
    ).count()

    ranking_digitadores = []
    for u in usuarios_staff:
        total_oficializados = Inscripcion.objects.filter(
            estado_solicitud='INSCRITO',
            inscrito_por=u
        ).count()
        oficializados_hoy = Inscripcion.objects.filter(
            estado_solicitud='INSCRITO',
            inscrito_por=u,
            fecha_oficializacion__date=hoy
        ).count()
        total_editados = Inscripcion.objects.filter(ultima_edicion_por=u).count()

        ultimo_contrato = Inscripcion.objects.filter(
            estado_solicitud='INSCRITO',
            inscrito_por=u
        ).order_by('-fecha_oficializacion').first()

        porcentaje_aporte = round((total_oficializados / total_contratos_global) * 100, 1) if total_contratos_global > 0 else 0

        nombre_completo = f"{u.first_name} {u.last_name}".strip() or u.username
        roles_str = ", ".join([
            g.name for g in u.groups.all()
            if 'digitador' in g.name.lower() or 'secretar' in g.name.lower()
        ])

        ranking_digitadores.append({
            'usuario': u,
            'nombre': nombre_completo,
            'username': u.username,
            'roles': roles_str,
            'total_oficializados': total_oficializados,
            'oficializados_hoy': oficializados_hoy,
            'total_editados': total_editados,
            'porcentaje_aporte': porcentaje_aporte,
            'ultimo_contrato': ultimo_contrato,
        })

    ranking_digitadores.sort(key=lambda x: (x['total_oficializados'], x['total_editados']), reverse=True)

    bitacora_qs = Inscripcion.objects.select_related(
        'estudiante', 'grado_a_cursar', 'inscrito_por', 'ultima_edicion_por'
    ).order_by('-fecha_oficializacion', '-fecha_ultima_edicion', '-id')

    if digitador_id:
        if digitador_id == 'sin_asignar':
            bitacora_qs = bitacora_qs.filter(inscrito_por__isnull=True)
        else:
            bitacora_qs = bitacora_qs.filter(
                Q(inscrito_por_id=digitador_id) | Q(ultima_edicion_por_id=digitador_id)
            )

    if fecha_filtro:
        bitacora_qs = bitacora_qs.filter(fecha_oficializacion__date=fecha_filtro)

    if query:
        bitacora_qs = bitacora_qs.filter(
            Q(correlativo_contrato__icontains=query) |
            Q(ticket_generado__icontains=query) |
            Q(estudiante__cui__icontains=query) |
            Q(estudiante__nombres__icontains=query) |
            Q(estudiante__apellidos__icontains=query)
        )

    context = {
        'ranking_digitadores': ranking_digitadores,
        'bitacora': bitacora_qs[:200],
        'total_contratos_global': total_contratos_global,
        'contratos_hoy_global': contratos_hoy_global,
        'sin_atribuir': sin_atribuir,
        'digitador_filtro': digitador_id,
        'fecha_filtro': fecha_filtro,
        'query': query,
        'hoy': hoy,
    }
    return render(request, 'portal_staff/panel_supervisor.html', context)