from django import forms
from personas.models import Estudiante, Responsable, EstudianteResponsable, ContactoEmergencia
from inscripciones.models import Inscripcion
from academico.models import CarreraCuota

# Opciones predefinidas para facilitar el llenado
OPCIONES_SANGRE = [('No lo sabe', 'No lo sabe'), ('O+', 'O+'), ('O-', 'O-'), ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-')]
OPCIONES_VIVE_CON = [('Ambos Padres', 'Ambos Padres'), ('Solo Madre', 'Solo Madre'), ('Solo Padre', 'Solo Padre'), ('Abuelos', 'Abuelos'), ('Tíos', 'Tíos'), ('Otro', 'Otro (Especificar abajo)')]
OPCIONES_ESTADO_CIVIL = [('Casado(a)', 'Casado(a)'), ('Soltero(a)', 'Soltero(a)'), ('Unido(a)', 'Unido(a)'), ('Divorciado(a)', 'Divorciado(a)'), ('Viudo(a)', 'Viudo(a)')]

class EstudianteForm(forms.ModelForm):
    tiene_enfermedad = forms.BooleanField(
        required=False, 
        label="¿Padece alguna enfermedad?", 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    genero = forms.ChoiceField(
        choices=[('Masculino', 'Masculino'), ('Femenino', 'Femenino')], 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    tipo_sangre = forms.ChoiceField(
        choices=OPCIONES_SANGRE, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    vive_con = forms.ChoiceField(
        choices=OPCIONES_VIVE_CON, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    depende_de = forms.ChoiceField(
        choices=OPCIONES_VIVE_CON, 
        widget=forms.Select(attrs={'class': 'form-select'}), 
        label="Depende económicamente de"
    )
    
    vive_con_otro = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Especifique con quién vive'})
    )
    depende_de_otro = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Especifique de quién depende'})
    )

    class Meta:
        model = Estudiante
        fields = [
            'nombres', 'apellidos', 'genero', 'fecha_nacimiento', 'edad', 'telefono', 
            'tipo_sangre', 'tiene_enfermedad', 'enfermedades_padece', 'impedimento_fisico', 
            'detalle_impedimento', 'vive_con', 'vive_con_otro', 'depende_de', 'depende_de_otro'
        ]
        labels = {
            'impedimento_fisico': '¿Tiene impedimento físico?',
        }
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'edad': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control telefono-internacional', 'placeholder': 'Ej. 12345678 (Opcional)'}),
            'enfermedades_padece': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Indique si padece asma, alergias, diabetes, etc.'}),
            'impedimento_fisico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'detalle_impedimento': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Especifique el impedimento físico.'}),
        }

    def __init__(self, *args, **kwargs):
        super(EstudianteForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.enfermedades_padece:
            self.fields['tiene_enfermedad'].initial = True
        
        # ELIMINAR VALIDACIÓN ESTRICTA HTML5
        for field in self.fields:
            self.fields[field].required = False

class ResponsableForm(forms.ModelForm):
    parentesco_tipo = forms.ChoiceField(
        choices=EstudianteResponsable.TIPO_PARENTESCO, 
        widget=forms.Select(attrs={'class': 'form-select'}), 
        label="¿Qué es del estudiante?"
    )
    estado_civil = forms.ChoiceField(
        choices=OPCIONES_ESTADO_CIVIL, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = Responsable
        fields = [
            'tipo_documento', 'dpi', 'nombres', 'apellidos', 'edad', 'estado_civil', 'direccion', 
            'celular', 'tiene_whatsapp', 'telefono_fijo', 
            'profesion', 'nacionalidad', 'religion', 'iglesia', 'correo_electronico'
        ]
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'dpi': forms.TextInput(attrs={'class': 'form-control dpi-input', 'placeholder': '13 dígitos sin espacios'}),
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'edad': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Edad'}),
            'direccion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),

            'celular': forms.TextInput(attrs={'class': 'form-control telefono-internacional', 'placeholder': 'Número sin guiones'}),
            'telefono_fijo': forms.TextInput(attrs={'class': 'form-control telefono-internacional', 'placeholder': 'Opcional'}),
            'tiene_whatsapp': forms.CheckboxInput(attrs={'class': 'form-check-input'}),

            'profesion': forms.TextInput(attrs={'class': 'form-control'}),
            'nacionalidad': forms.TextInput(attrs={'class': 'form-control'}),
            'religion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'iglesia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'correo_electronico': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ELIMINAR VALIDACIÓN ESTRICTA HTML5
        for field in self.fields:
            self.fields[field].required = False
            
        # NUEVO: Evitar que Django rechace el formulario si el DPI ya existe
        # Esto permite que views.py atrape el dato y simplemente lo asocie al nuevo estudiante
        if 'dpi' in self.fields:
            self.fields['dpi'].validators = []

class PreinscripcionForm(forms.ModelForm):
    es_nuevo_ingreso = forms.BooleanField(
        required=False, 
        label="¿Es estudiante de Primer Ingreso al colegio?", 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    grado_a_cursar = forms.ModelChoiceField(
        queryset=CarreraCuota.objects.all().order_by('orden', 'nivel_educativo', 'grado'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Grado a cursar en el próximo ciclo"
    )

    class Meta:
        model = Inscripcion
        fields = ['grado_a_cursar', 'colegio_anterior', 'promedio', 'razon_retiro']
        widgets = {
            'colegio_anterior': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Especifique el colegio anterior'}),
            'promedio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'razon_retiro': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ELIMINAR VALIDACIÓN ESTRICTA HTML5
        for field in self.fields:
            self.fields[field].required = False

class ContactoEmergenciaForm(forms.ModelForm):
    class Meta:
        model = ContactoEmergencia
        fields = ['nombre_completo', 'parentesco', 'celular']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la persona a avisar'}),
            'parentesco': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Abuela, Tío, Vecino'}),
            'celular': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].required = False