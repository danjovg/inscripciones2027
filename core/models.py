from django.db import models

class ConfiguracionAnual(models.Model):
    anio_ciclo = models.IntegerField(unique=True, default=2027, verbose_name="Año del Ciclo Escolar")
    anio_ciclo_letras = models.CharField(
        max_length=100, 
        default="dos mil veintisiete",
        help_text="Se usa en la Cláusula Tercera (Plazo). Ej: dos mil veintisiete"
    )
    datos_representante_legal = models.TextField(
        help_text="Nombres, DPI, Edad, Estado Civil, Profesión, Dirección, Datos de Notario y Partida"
    )
    texto_resolucion_diaco = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        default="DDC-________-20__",
        help_text="Si aún no la tiene, déjelo con guiones bajos o en blanco."
    )
    resoluciones_dideduc_servicios = models.TextField(
        blank=True,
        null=True,
        default="a) No. 1664-2024/ Dideduc-Chiq, de fecha 16 de diciembre de 2024; b) No. 1100-2025 Dideduc-Chiq de fecha 21 de noviembre de 2025; c) No. 1099-2025 Dideduc-Chiq de fecha 21 de noviembre de 2025; d) No. 422-2020/Dideduc-Chiq, de fecha 12 de octubre de 2020; e) No. 423-2020 Dideduc-Chiq de fecha 12 de octubre de 2020",
        help_text="Resoluciones DIDEDUC que aparecen en la Cláusula Primera."
    )
    resoluciones_dideduc_cuotas = models.TextField(
        blank=True,
        null=True,
        default="No.576-2025, de fecha 30 de julio del 2025, emitida y resolución No.999-2025, de fecha 21 de octubre de 2025",
        help_text="Resoluciones DIDEDUC que autorizan las cuotas en la Cláusula Sexta."
    )
    monto_mora = models.DecimalField(max_digits=8, decimal_places=2, default=20.00)
    plantilla_contrato_html = models.TextField(
        blank=True, 
        null=True,
        help_text="Opcional. Si se deja en blanco, usa la plantilla oficial DIACO 2027 integrada."
    )
    prefijo_correlativo = models.CharField(max_length=10, default="CA-")
    correlativo_actual = models.IntegerField(default=1)
    firma_representante_legal = models.ImageField(
        upload_to='firmas_legales/',
        null=True,
        blank=True,
        help_text="Firma digitalizada en formato PNG transparente."
    )
    

    def __str__(self):
        return f"Ciclo Escolar {self.anio_ciclo}"


class ConsentimientoConfig(models.Model):
    ciclo = models.ForeignKey(ConfiguracionAnual, on_delete=models.CASCADE)
    pregunta = models.CharField(max_length=200)
    es_obligatorio = models.BooleanField(default=True)

    def __str__(self):
        return self.pregunta


class CuotaMineducContrato(models.Model):
    """
    Tabla exclusiva para imprimir las dos tablas de la Cláusula Sexta del Contrato 2027.
    No afecta los selectores de grados públicos ni el control de cupos.
    """
    JORNADA_CHOICES = (
        ('MATUTINA', 'Jornada Matutina'),
        ('VESPERTINA', 'Jornada Vespertina'),
    )
    ciclo = models.ForeignKey(ConfiguracionAnual, on_delete=models.CASCADE, related_name='cuotas_mineduc')
    jornada = models.CharField(max_length=20, choices=JORNADA_CHOICES, default='VESPERTINA')
    orden = models.PositiveIntegerField(default=1, help_text="Orden de aparición (1=Preprimaria, 2=Primaria, 3=Básico...)")
    
    nivel_educacion = models.CharField(
        max_length=150,
        verbose_name="Nivel / Carrera en Contrato",
        help_text="Ej: PREPRIMARIA, PRIMARIA, BÁSICO, PERITO EN ADMINISTRACIÓN DE EMPRESAS..."
    )
    
    # 1. Montos reales a cobrar por el Colegio (Primera tabla de la Cláusula Sexta)
    inscripcion_colegio = models.DecimalField(
        max_digits=8, decimal_places=2, default=0.00,
        verbose_name="Inscripción a Cobrar Colegio (Q)"
    )
    mensualidad_colegio = models.DecimalField(
        max_digits=8, decimal_places=2, default=0.00,
        verbose_name="Mensualidad a Cobrar Colegio (Q)"
    )

    # 2. Montos techo autorizados según Resolución MINEDUC (Segunda tabla de la Cláusula Sexta)
    inscripcion = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name="Inscripción Autorizada MINEDUC (Q)"
    )
    colegiatura_mensual = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name="Mensualidad Autorizada MINEDUC (Q)"
    )

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Cuota de Contrato (Colegio y MINEDUC)"
        verbose_name_plural = "Cuotas de Contrato (Colegio y MINEDUC)"

    def __str__(self):
        return f"{self.nivel_educacion} | Cobro: Q.{self.inscripcion_colegio}/Q.{self.mensualidad_colegio} | MINEDUC: Q.{self.inscripcion}/Q.{self.colegiatura_mensual}"


class ControlEstadoSistema(models.Model):
    """
    Tabla independiente para controlar los dos bloqueos maestros del sistema:
    1) Suspensión administrativa por falta de pago.
    2) Cierre de horario/jornada de trabajo para Digitadores y Auxiliares.
    """
    nombre_control = models.CharField(
        max_length=100,
        default="Control Maestro de Acceso (Gestión y Docentes)",
        editable=False
    )

    # --- INTERRUPTOR 1: SUSPENSIÓN POR FALTA DE PAGO ---
    bloqueo_por_pago = models.BooleanField(
        default=False,
        verbose_name="🔴 1. Suspender por Falta de Pago",
        help_text="Si se activa, bloquea totalmente Gestión y Docentes mostrando el aviso de facturación pendiente."
    )
    mensaje_pago = models.TextField(
        default="El acceso a los portales administrativos y docentes se encuentra temporalmente suspendido por renovación o pago pendiente de soporte y plataforma.",
        verbose_name="Mensaje en pantalla de Falta de Pago"
    )

    # --- INTERRUPTOR 2: CIERRE DE JORNADA DE INSCRIPCIONES (FUERA DE HORARIO) ---
    cierre_jornada_laboral = models.BooleanField(
        default=False,
        verbose_name="🌙 2. Cerrar Jornada de Inscripciones (Fuera de Horario)",
        help_text="Actívelo al terminar el horario del colegio para que ningún Digitador ni Auxiliar pueda entrar o generar contratos de noche."
    )
    horario_atencion_texto = models.CharField(
        max_length=150,
        default="Lunes a Viernes de 7:30 AM a 4:30 PM",
        verbose_name="Horario habilitado a mostrar en pantalla"
    )
    mensaje_jornada = models.TextField(
        default="La jornada de inscripciones y emisión de contratos ha finalizado por el día de hoy. El sistema volverá a estar habilitado en el próximo horario laboral.",
        verbose_name="Mensaje en pantalla de Jornada Cerrada"
    )
    permitir_direccion_en_cierre = models.BooleanField(
        default=True,
        verbose_name="Permitir vista a Dirección cuando la jornada esté cerrada",
        help_text="Si está marcado, cuando cierres la jornada de los Digitadores, Dirección aún podrá entrar a ver las estadísticas."
    )

    ultima_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Control de Estado y Horario del Sistema"
        verbose_name_plural = "Control de Estado y Horario del Sistema"

    def __str__(self):
        estados = []
        if self.bloqueo_por_pago:
            estados.append("🔴 SUSPENDIDO POR PAGO")
        if self.cierre_jornada_laboral:
            estados.append("🌙 JORNADA CERRADA")
        if not estados:
            estados.append("🟢 SISTEMA HABILITADO")
        return f"{self.nombre_control} — {' | '.join(estados)}"