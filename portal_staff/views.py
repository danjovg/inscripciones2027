import base64
import json
import os
import random
import string
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

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
# VALIDADORES DE PERMISOS POR ROL
# =========================================================================
def es_personal_administrativo(user):
    """Permite acceso a Auxiliares, Digitadores, Secretaría, Dirección o Superusuario."""
    return user.is_superuser or user.groups.filter(
        name__in=['Auxiliares', 'Digitadores', 'Secretaría General', 'Dirección']
    ).exists()


def es_digitador_o_superior(user):
    """Bloquea a los Auxiliares para que no entren al módulo de Digitadores."""
    return user.is_superuser or user.groups.filter(
        name__in=['Digitadores', 'Secretaría General', 'Dirección']
    ).exists()


def es_direccion(user):
    """Solo usuarios del grupo Dirección o Superusuarios entran al Dashboard Ejecutivo."""
    return user.is_superuser or user.groups.filter(name='Dirección').exists()


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
        sigla_jornada = 'JM'

    return f"{prefijo}{numero}-{sigla_jornada}-{anio}"


# =========================================================================
# VISTAS DEL ROL: AUXILIAR (PUERTA)
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_personal_administrativo, login_url='/accounts/login/')
def dashboard_auxiliar(request):
    """Buscador rápido en puerta por CUI, Nombres o Apellidos."""
    query = request.GET.get('q', '').strip()
    resultados = []

    if query:
        resultados = Estudiante.objects.filter(
            Q(cui__icontains=query) |
            Q(nombres__icontains=query) |
            Q(apellidos__icontains=query)
        )

    context = {
        'resultados': resultados,
        'query': query,
    }
    return render(request, 'portal_staff/dashboard.html', context)


@login_required(login_url='/accounts/login/')
@user_passes_test(es_personal_administrativo, login_url='/accounts/login/')
def generar_ticket_rapido(request):
    """Crea un expediente rápido en BORRADOR para padres que llegan sin preinscripción."""
    if request.method == 'POST':
        cui = request.POST.get('cui', '').strip()
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
            }
        )

        if not inscripcion.ticket_generado:
            inscripcion.ticket_generado = generar_codigo_ticket()
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
        self.fields['grado_a_cursar'].queryset = CarreraCuota.objects.all()
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


# =========================================================================
# VISTAS DEL ROL: DIGITADOR
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_digitador_o_superior, login_url='/accounts/login/')
def panel_digitador(request):
    """Bandeja del Digitador con pestañas de Pendientes, Inscritos y Todos."""
    query = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', 'pendientes')

    if filtro_estado == 'inscritos':
        inscripciones_qs = Inscripcion.objects.filter(estado_solicitud='INSCRITO').select_related('estudiante', 'grado_a_cursar').order_by('-id')
    elif filtro_estado == 'todos':
        inscripciones_qs = Inscripcion.objects.all().select_related('estudiante', 'grado_a_cursar').order_by('-id')
    else:
        inscripciones_qs = Inscripcion.objects.exclude(estado_solicitud='INSCRITO').select_related('estudiante', 'grado_a_cursar').order_by('-id')

    if query:
        inscripciones_filtradas = inscripciones_qs.filter(
            Q(ticket_generado__icontains=query) |
            Q(correlativo_contrato__icontains=query) |
            Q(estudiante__cui__icontains=query) |
            Q(estudiante__nombres__icontains=query) |
            Q(estudiante__apellidos__icontains=query)
        )
        if not inscripciones_filtradas.exists() and filtro_estado == 'pendientes':
            inscripciones_filtradas = Inscripcion.objects.filter(
                Q(ticket_generado__icontains=query) |
                Q(correlativo_contrato__icontains=query) |
                Q(estudiante__cui__icontains=query) |
                Q(estudiante__nombres__icontains=query) |
                Q(estudiante__apellidos__icontains=query)
            ).select_related('estudiante', 'grado_a_cursar').order_by('-id')
            filtro_estado = 'todos'
        inscripciones_qs = inscripciones_filtradas

    total_pendientes = Inscripcion.objects.exclude(estado_solicitud='INSCRITO').count()
    total_inscritos = Inscripcion.objects.filter(estado_solicitud='INSCRITO').count()

    context = {
        'inscripciones': inscripciones_qs,
        'query': query,
        'filtro_estado': filtro_estado,
        'total_pendientes': total_pendientes,
        'total_inscritos': total_inscritos,
    }
    return render(request, 'portal_staff/panel_digitador.html', context)


@login_required(login_url='/accounts/login/')
@user_passes_test(es_digitador_o_superior, login_url='/accounts/login/')
def editar_expediente_digitador(request, inscripcion_id):
    """Vista de auditoría completa: Sección A (Alumno), Sección B (Responsables) y Sección C (Emergencias)."""
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
            dpi_ingresado = request.POST.get('dpi', '').strip()
            instancia_resp = Responsable.objects.filter(dpi=dpi_ingresado).first()
            form_responsable = ResponsableForm(request.POST, instance=instancia_resp)

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
                messages.success(request, f'✅ Responsable {resp_obj.nombres} {resp_obj.apellidos} guardado correctamente.')
                return redirect(f"/digitador/editar/{inscripcion.id}/#seccion-responsables")
            else:
                messages.error(request, '⚠️ No se pudo guardar el responsable. Revise los campos marcados en la Sección B.')

        # ACCIÓN B: CAMBIAR QUIÉN FIRMA EL CONTRATO ESE DÍA
        elif accion == 'hacer_principal':
            vinculo_id = request.POST.get('vinculo_id')
            EstudianteResponsable.objects.filter(estudiante=estudiante).update(es_contacto_principal=False)
            EstudianteResponsable.objects.filter(id=vinculo_id, estudiante=estudiante).update(es_contacto_principal=True)
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
                messages.success(request, f'✅ Contacto de emergencia "{emerg_obj.nombre_completo}" agregado.')
                return redirect(f"/digitador/editar/{inscripcion.id}/#seccion-emergencias")
            else:
                messages.error(request, 'Error al agregar contacto de emergencia.')

        # ACCIÓN E: ELIMINAR CONTACTO DE EMERGENCIA
        elif accion == 'eliminar_emergencia':
            emergencia_id = request.POST.get('emergencia_id')
            ContactoEmergencia.objects.filter(id=emergencia_id, estudiante=estudiante).delete()
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

                    es_dir = request.user.is_superuser or request.user.groups.filter(name='Dirección').exists()
                    if hasattr(grado, 'cupos_ocupados') and hasattr(grado, 'cupo_maximo'):
                        if inscripcion.estado_solicitud != 'INSCRITO' and grado.cupos_ocupados >= grado.cupo_maximo and not es_dir:
                            messages.error(request, f'⚠️ ¡Cupo lleno en {grado}! Solicite autorización a Dirección para inscribirlo.')
                            return redirect('editar_expediente', inscripcion_id=inscripcion.id)

                        if inscripcion.estado_solicitud != 'INSCRITO':
                            grado.cupos_ocupados += 1
                            grado.save()

                    # Generar correlativo oficial (CA-002-JV-2027) si aún no lo tiene
                    if not insc_obj.correlativo_contrato:
                        config = ConfiguracionAnual.objects.filter(anio_ciclo=grado.ciclo.anio_ciclo).first() or ConfiguracionAnual.objects.last()
                        if config:
                            insc_obj.correlativo_contrato = construir_correlativo_oficial(config, grado)
                            config.correlativo_actual += 1
                            config.save()

                    insc_obj.estado_solicitud = 'INSCRITO'
                    insc_obj.save()

                    return redirect('descargar_contrato_pdf', inscripcion_id=inscripcion.id)

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

    total_cupo_colegio = 0
    total_inscritos_colegio = 0
    total_en_proceso_colegio = 0
    grados_llenos = 0

    datos_grados = []

    for c in carreras:
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
# GENERACIÓN DEL CONTRATO DIACO Y FICHA INFORMATIVA (TAMAÑO OFICIO)
# =========================================================================
@login_required(login_url='/accounts/login/')
@user_passes_test(es_digitador_o_superior, login_url='/accounts/login/')
def descargar_contrato_pdf(request, inscripcion_id):
    """
    Genera el Contrato de Adhesión DIACO y la Ficha Informativa en tamaño Oficio.
    """
    inscripcion = get_object_or_404(Inscripcion, id=inscripcion_id)
    estudiante = inscripcion.estudiante
    grado = inscripcion.grado_a_cursar

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

    # 1. Asegurar correlativo oficial con formato CA-002-JV-2027 (o JM según jornada)
    if not inscripcion.correlativo_contrato and config:
        inscripcion.correlativo_contrato = construir_correlativo_oficial(config, grado)
        config.correlativo_actual += 1
        config.save()
        inscripcion.save(update_fields=['correlativo_contrato'])

    correlativo = inscripcion.correlativo_contrato or f"CA-{inscripcion.id:03d}-JV-2027"

    # 2. Poblar valores iniciales de Cuotas MINEDUC si aún no existen en la BD para este ciclo
    if config and not CuotaMineducContrato.objects.filter(ciclo=config).exists():
        datos_iniciales = [
            ('MATUTINA', 1, 'Preprimaria', '608.35', '395.43'),
            ('MATUTINA', 2, 'Primaria', '608.35', '395.43'),
            ('VESPERTINA', 1, 'Ciclo Básico', '661.25', '462.88'),
            ('VESPERTINA', 2, 'Bachillerato en Ciencias y Letras con Orientación en Computación', '793.50', '634.80'),
            ('VESPERTINA', 3, 'Perito en Administración de Empresas', '793.50', '502.55'),
        ]
        for jorn, ord_num, niv, insc_val, mens_val in datos_iniciales:
            CuotaMineducContrato.objects.create(
                ciclo=config,
                jornada=jorn,
                orden=ord_num,
                nivel_educacion=niv,
                inscripcion=insc_val,
                colegiatura_mensual=mens_val,
            )

    cuotas_matutina = CuotaMineducContrato.objects.filter(ciclo=config, jornada='MATUTINA').order_by('orden') if config else []
    cuotas_vespertina = CuotaMineducContrato.objects.filter(ciclo=config, jornada='VESPERTINA').order_by('orden') if config else []

    # 3. Convertir la imagen PNG de la firma a Base64 directo desde el disco para que siempre se muestre
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

    # 4. Fecha en español
    meses_es = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
        7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    anios_texto = {
        2026: 'dos mil veintiséis',
        2027: 'dos mil veintisiete',
        2028: 'dos mil veintiocho',
    }
    hoy = date.today()

    if getattr(responsable, 'tipo_documento', 'DPI') == 'Pasaporte':
        frase_documento = "Pasaporte número"
    else:
        frase_documento = "Documento Personal de Identificación -DPI- con Código Único de Identificación -CUI- número"

    sigla_jornada_ficha = 'JM' if 'MATUTINA' in (grado.jornada or '').upper() else 'JV'
    forzar_pdf = request.GET.get('forzar_pdf') == '1'

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
        'cuotas_matutina': cuotas_matutina,
        'cuotas_vespertina': cuotas_vespertina,
        'firma_base64': firma_base64,
        'fecha_dia': hoy.day,
        'fecha_mes': meses_es.get(hoy.month, ''),
        'fecha_anio': hoy.year,
        'fecha_anio_texto': anios_texto.get(hoy.year, str(hoy.year)),
        'frase_documento': frase_documento,
        'url_base': f"{request.scheme}://{request.get_host()}",
        'modo_weasyprint': forzar_pdf,
    }

    if forzar_pdf:
        try:
            from weasyprint import HTML
            html_string = render_to_string('portal_staff/contrato_pdf.html', context, request=request)
            pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Contrato_{correlativo}_{estudiante.cui}.pdf"'
            return response
        except Exception:
            context['modo_weasyprint'] = False

    return render(request, 'portal_staff/contrato_pdf.html', context)