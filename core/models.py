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
        default="a) No. 882-2019/ Dideduc-Chiq, de fecha 25 de noviembre de 2019; b) No. 422-2020 Dideduc-Chiq de fecha 12 de octubre de 2020; c) No. 423-2020 Dideduc-Chiq de fecha 12 de octubre de 2020; d) No. 424-2020/Dideduc-Chiq, de fecha 12 de octubre de 2020; e) No. 813-2021 Dideduc-Chiq de fecha 18 de octubre de 2021",
        help_text="Resoluciones DIDEDUC que aparecen en la Cláusula Primera."
    )
    resoluciones_dideduc_cuotas = models.TextField(
        blank=True,
        null=True,
        default="No. 576-2025 DIDEDUC-CHIQ de fecha 30 de julio del año 2025, No. 489-2022 DIDEDUC-CHIQ de fecha 03 de junio de 2022",
        help_text="Resoluciones DIDEDUC que autorizan las cuotas en la Cláusula Sexta."
    )
    monto_mora = models.DecimalField(max_digits=8, decimal_places=2, default=10.00)
    plantilla_contrato_html = models.TextField(
        blank=True, 
        null=True,
        help_text="Opcional. Si se deja en blanco, usa la plantilla oficial DIACO integrada."
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
    Tabla exclusiva para los valores fijos autorizados por MINEDUC que se imprimen
    en la Cláusula Sexta del Contrato (divididos en Jornada Matutina y Vespertina).
    """
    JORNADA_CHOICES = (
        ('MATUTINA', 'Jornada Matutina'),
        ('VESPERTINA', 'Jornada Vespertina'),
    )
    ciclo = models.ForeignKey(ConfiguracionAnual, on_delete=models.CASCADE, related_name='cuotas_mineduc')
    jornada = models.CharField(max_length=20, choices=JORNADA_CHOICES, default='VESPERTINA')
    orden = models.PositiveIntegerField(default=1, help_text="Orden en que aparece en la tabla del contrato (1, 2, 3...)")
    nivel_educacion = models.CharField(
        max_length=150,
        help_text="Ej: Preprimaria, Primaria, Ciclo Básico, Bachillerato en Ciencias y Letras con Orientación en Computación..."
    )
    inscripcion = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Inscripción (Q)")
    colegiatura_mensual = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Colegiatura Mensual (Q)")

    class Meta:
        ordering = ['jornada', 'orden', 'id']
        verbose_name = "Cuota Autorizada MINEDUC (Contrato)"
        verbose_name_plural = "Cuotas Autorizadas MINEDUC (Contrato)"

    def __str__(self):
        return f"{self.get_jornada_display()} - {self.nivel_educacion} (Insc: Q.{self.inscripcion} | Mens: Q.{self.colegiatura_mensual})"