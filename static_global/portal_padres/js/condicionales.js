document.addEventListener('DOMContentLoaded', function() {
    // 1. LÓGICA DE GRADOS DESDE LA CONFIGURACIÓN DE DJANGO ADMIN
    const gradoSelect = document.getElementById('id_insc-grado_a_cursar');
    const checkboxNuevo = document.getElementById('id_insc-es_nuevo_ingreso');
    const checkboxDiv = checkboxNuevo ? checkboxNuevo.closest('.form-check') : null;
    
    const colegioAnteriorDiv = document.getElementById('div_id_insc-colegio_anterior');
    const promedioDiv = document.getElementById('div_id_insc-promedio');
    const razonRetiroDiv = document.getElementById('div_id_insc-razon_retiro');

    const colegioInput = document.getElementById('id_insc-colegio_anterior');
    const promedioInput = document.getElementById('id_insc-promedio');
    const razonInput = document.getElementById('id_insc-razon_retiro');

    // Recupera la configuración que pasamos desde la vista
    const configGrados = window.DJANGO_CONFIG_GRADOS || {};

    function evaluarCamposGrado() {
        if (!gradoSelect) return;
        
        // Obtenemos el ID de la carrera actual (ej: "1", "2")
        const gradoId = gradoSelect.value.toString();
        // Leemos la configuración enviada desde Django ('OBLIGATORIO', 'MANUAL', 'OCULTO')
        const config = configGrados[gradoId] || 'MANUAL'; 
        
        let esNuevo = checkboxNuevo ? checkboxNuevo.checked : false;

        // Reset visual del checkbox para evitar que se quede pegado o invisible
        if(checkboxDiv) checkboxDiv.style.display = 'block';

        if (config === 'OBLIGATORIO') {
            if(checkboxDiv) checkboxDiv.style.display = 'none'; // Oculta el check porque es obligatorio
            esNuevo = true;
        } else if (config === 'OCULTO') {
            if(checkboxDiv) checkboxDiv.style.display = 'none';
            esNuevo = false;
        } else if (config === 'MANUAL') {
            if(checkboxDiv) checkboxDiv.style.display = 'block'; // Muestra la opción
        }

        const mostrar = esNuevo ? 'block' : 'none';
        
        if(colegioAnteriorDiv) colegioAnteriorDiv.style.display = mostrar;
        if(promedioDiv) promedioDiv.style.display = mostrar;
        if(razonRetiroDiv) razonRetiroDiv.style.display = mostrar;

        // Obligatoriedad Dinámica para evitar validaciones erróneas en Backend
        if (esNuevo) {
            if(colegioInput) colegioInput.setAttribute('required', 'required');
        } else {
            if(colegioInput) colegioInput.removeAttribute('required');
            if(promedioInput) promedioInput.removeAttribute('required');
            if(razonInput) razonInput.removeAttribute('required');

            if(colegioInput) colegioInput.value = '';
            if(promedioInput) promedioInput.value = '';
            if(razonInput) razonInput.value = '';
        }
    }

    if (gradoSelect) gradoSelect.addEventListener('change', evaluarCamposGrado);
    if (checkboxNuevo) checkboxNuevo.addEventListener('change', evaluarCamposGrado);
    
// 2. LÓGICA DE "VIVE CON OTRO" Y "DEPENDE DE OTRO"
    function setupConditionalField(selectId, inputId) {
        const select = document.getElementById(selectId);
        const input = document.getElementById(inputId);
        
        if (select && input) {
            // Buscamos el contenedor padre (el div de Bootstrap/Crispy)
            const container = input.closest('div.mb-3') || input.parentElement;
            
            // Función interna para evaluar y mostrar/ocultar
            const evaluate = () => {
                const show = select.value === 'Otro'; // Revisa que coincida EXACTAMENTE con 'Otro' o 'Otro (Especificar abajo)'
                // Si el valor seleccionado contiene la palabra 'Otro', mostramos
                if (select.value.includes('Otro')) {
                    container.style.display = 'block';
                } else {
                    container.style.display = 'none';
                    input.value = ''; // Limpiar si ocultan
                }
            };

            // Ejecutar al cargar la página
            evaluate();
            
            // Ejecutar cada vez que el usuario cambia la opción
            select.addEventListener('change', evaluate);
        }
    }

    // Inicializamos ambas lógicas llamando a los IDs exactos de los inputs
    setupConditionalField('id_est-vive_con', 'id_est-vive_con_otro');
    setupConditionalField('id_est-depende_de', 'id_est-depende_de_otro');

    // 3. LÓGICA DE ENFERMEDADES E IMPEDIMENTOS FÍSICOS
    function toggleCheckboxField(checkboxId, fieldDivId) {
        const checkbox = document.getElementById(checkboxId);
        const fieldDiv = document.getElementById(fieldDivId);
        
        if (checkbox && fieldDiv) {
            // 1. Ocultar o mostrar al cargar la página según si está marcado
            fieldDiv.style.display = checkbox.checked ? 'block' : 'none';
            
            // 2. Escuchar cambios cuando el usuario hace clic
            checkbox.addEventListener('change', () => {
                fieldDiv.style.display = checkbox.checked ? 'block' : 'none';
                
                // Si el usuario desmarca la casilla, limpiamos lo que había escrito
                if (!checkbox.checked) {
                    const inputField = document.getElementById(fieldDivId.replace('div_id_', 'id_'));
                    if(inputField) inputField.value = '';
                }
            });
        }
    }

    // Inicializamos el toggle para Enfermedades
    toggleCheckboxField('id_est-tiene_enfermedad', 'div_id_est-enfermedades_padece');
    
    // Inicializamos el toggle para Impedimentos Físicos
    toggleCheckboxField('id_est-impedimento_fisico', 'div_id_est-detalle_impedimento');

    // Usamos setTimeout para que se ejecute después de que se rendericen los forms 
    setTimeout(evaluarCamposGrado, 100);

    // 4. LÓGICA DE CÁLCULO DE EDAD AUTOMÁTICO
    const fechaNacimientoInput = document.getElementById('id_est-fecha_nacimiento');
    const edadInput = document.getElementById('id_est-edad');

    function calcularEdad() {
        if (fechaNacimientoInput && fechaNacimientoInput.value) {
            const fechaNacimiento = new Date(fechaNacimientoInput.value);
            const hoy = new Date();
            
            let edad = hoy.getFullYear() - fechaNacimiento.getFullYear();
            const mes = hoy.getMonth() - fechaNacimiento.getMonth();
            
            // Si aún no hemos llegado al mes de cumpleaños, o estamos en el mes pero no hemos llegado al día
            if (mes < 0 || (mes === 0 && hoy.getDate() < fechaNacimiento.getDate())) {
                edad--;
            }
            
            if (edadInput) {
                edadInput.value = edad;
            }
        } else if (edadInput) {
             edadInput.value = ''; // Limpiar si borran la fecha
        }
    }

    if (fechaNacimientoInput) {
        // Calcular al cambiar la fecha o al teclear
        fechaNacimientoInput.addEventListener('change', calcularEdad);
        fechaNacimientoInput.addEventListener('input', calcularEdad);
        
        // Calcular al cargar la página por si ya hay un valor guardado (Borrador/Reinscripción)
        calcularEdad(); 
    }
});