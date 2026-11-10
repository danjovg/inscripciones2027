from django.db import models
from datetime import date

class Responsable(models.Model):
    dpi = models.CharField(max_length=15, primary_key=True)
    tipo_documento = models.CharField(max_length=20, choices=[('DPI', 'DPI'), ('Pasaporte', 'Pasaporte')], default='DPI')
    nombres = models.CharField(max_length=100, blank=True, null=True)
    apellidos = models.CharField(max_length=100, blank=True, null=True)
    edad = models.IntegerField(blank=True, null=True)
    estado_civil = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    
    celular = models.CharField(max_length=20, blank=True, null=True)
    telefono_fijo = models.CharField(max_length=20, blank=True, null=True)
    tiene_whatsapp = models.BooleanField(default=True, verbose_name="¿Tiene WhatsApp?")
    
    profesion = models.CharField(max_length=100, blank=True, null=True)
    nacionalidad = models.CharField(max_length=50, default='Guatemalteca', blank=True, null=True)
    religion = models.CharField(max_length=50, blank=True, null=True)
    iglesia = models.CharField(max_length=100, blank=True, null=True)
    correo_electronico = models.EmailField(blank=True, null=True)

    def __str__(self):
        if self.nombres and self.apellidos:
            return f"{self.nombres} {self.apellidos} - DPI: {self.dpi}"
        return f"Responsable sin nombre - DPI: {self.dpi}"

class Estudiante(models.Model):
    cui = models.CharField(max_length=13, primary_key=True)
    nombres = models.CharField(max_length=100, blank=True, null=True)
    apellidos = models.CharField(max_length=100, blank=True, null=True)
    genero = models.CharField(max_length=15, choices=[('Masculino', 'Masculino'), ('Femenino', 'Femenino')], blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    edad = models.IntegerField(blank=True, null=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    tipo_sangre = models.CharField(max_length=15, blank=True, null=True)
    
    enfermedades_padece = models.TextField(blank=True, null=True)
    impedimento_fisico = models.BooleanField(default=False)
    detalle_impedimento = models.TextField(blank=True, null=True)
    
    vive_con = models.CharField(max_length=100, blank=True, null=True)
    vive_con_otro = models.CharField(max_length=100, blank=True, null=True)
    depende_de = models.CharField(max_length=100, blank=True, null=True)
    depende_de_otro = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.fecha_nacimiento:
            from datetime import date
            today = date.today()
            self.edad = today.year - self.fecha_nacimiento.year - ((today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
        super().save(*args, **kwargs)

    def __str__(self):
            if self.nombres and self.apellidos:
                return f"{self.apellidos}, {self.nombres} - CUI: {self.cui}"
            return f"Estudiante sin nombre - CUI: {self.cui}"

class EstudianteResponsable(models.Model):
    TIPO_PARENTESCO = (
        ('Padre', 'Padre'),
        ('Madre', 'Madre'),
        ('Abuelo(a)', 'Abuelo(a)'),
        ('Tío(a)', 'Tío(a)'),
        ('Hermano(a)', 'Hermano(a)'),
        ('Representante Legal / Encargado', 'Representante Legal / Encargado'),
    )
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    responsable = models.ForeignKey(Responsable, on_delete=models.CASCADE)
    parentesco = models.CharField(max_length=50, choices=TIPO_PARENTESCO)
    es_contacto_principal = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.estudiante.nombres} - {self.responsable.nombres} ({self.parentesco})"

# Agregar la tabla de Contactos de Emergencia
class ContactoEmergencia(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='emergencias')
    nombre_completo = models.CharField(max_length=150)
    parentesco = models.CharField(max_length=50)
    celular = models.CharField(max_length=15)
    
    def __str__(self):
        return f"{self.nombre_completo} - {self.celular}"