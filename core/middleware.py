# core/middleware.py
import unicodedata
from django.shortcuts import render
from core.models import ControlEstadoSistema


def _normalizar(texto):
    if not texto:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower().strip())
        if unicodedata.category(c) != 'Mn'
    )


class ControlAccesoSistemaMiddleware:
    """
    Evalúa la tabla ControlEstadoSistema en cada petición hacia 'gestion' o 'docentes'.
    - El portal público de padres (inscripciones) siempre queda libre.
    - La ruta /super-admin/ y tu cuenta de Superusuario siempre tienen paso libre.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        host = request.get_host().lower()

        # 1. Nunca bloquear el Super-Admin, el login/logout ni los archivos estáticos
        if (
            path.startswith('/super-admin/')
            or path.startswith('/static/')
            or path.startswith('/media/')
            or path.startswith('/accounts/logout/')
        ):
            return self.get_response(request)

        # 2. Si eres tú (Superusuario), siempre tienes paso libre para probar y auditar
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
            return self.get_response(request)

        es_gestion = 'gestion' in host
        es_docentes = 'docentes' in host

        if es_gestion or es_docentes:
            control, _ = ControlEstadoSistema.objects.get_or_create(id=1)

            # CASO 1: SUSPENSIÓN POR FALTA DE PAGO (Aplica a Gestión y Docentes)
            if control.bloqueo_por_pago:
                return render(
                    request,
                    'portal_staff/sistema_suspendido.html',
                    {
                        'tipo_bloqueo': 'PAGO',
                        'control': control,
                    },
                    status=503
                )

            # CASO 2: CIERRE DE JORNADA DE INSCRIPCIONES (Aplica a Gestión: Digitadores/Auxiliares)
            if es_gestion and control.cierre_jornada_laboral:
                # Permitir que puedan ver la pantalla de login o cerrar sesión, pero bloquear adentro
                if not path.startswith('/accounts/login/'):
                    # Verificar si es Dirección y tiene permiso de consulta en cierre
                    if hasattr(request, 'user') and request.user.is_authenticated and control.permitir_direccion_en_cierre:
                        grupos = [_normalizar(g.name) for g in request.user.groups.all()]
                        es_dir = any('direccion' in g for g in grupos)
                        if es_dir:
                            return self.get_response(request)

                    return render(
                        request,
                        'portal_staff/sistema_suspendido.html',
                        {
                            'tipo_bloqueo': 'JORNADA',
                            'control': control,
                        },
                        status=403
                    )

        return self.get_response(request)