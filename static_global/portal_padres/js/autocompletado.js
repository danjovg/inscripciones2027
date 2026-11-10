document.addEventListener('DOMContentLoaded', function() {
    const dpiInput = document.getElementById('id_resp-dpi'); // Asegúrate que este sea el ID de tu campo en HTML
    
    if (dpiInput) {
        dpiInput.addEventListener('blur', function() {
            const dpiValue = this.value.trim();
            
            if (dpiValue.length >= 13) {
                // Hacer la petición AJAX al backend
                fetch(`/api/buscar-dpi/${dpiValue}/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.existe) {
                            // Se eliminó la línea "alert('Datos del familiar encontrados...');"
                            
                            // Autocompletar los campos si el padre/madre existe en DB
                            document.getElementById('id_resp-nombres').value = data.nombres || '';
                            document.getElementById('id_resp-apellidos').value = data.apellidos || '';
                            document.getElementById('id_resp-estado_civil').value = data.estado_civil || '';
                            document.getElementById('id_resp-direccion').value = data.direccion || '';
                            document.getElementById('id_resp-celular').value = data.celular || '';
                            document.getElementById('id_resp-telefono_fijo').value = data.telefono_fijo || '';
                            document.getElementById('id_resp-profesion').value = data.profesion || '';
                            document.getElementById('id_resp-nacionalidad').value = data.nacionalidad || '';
                            document.getElementById('id_resp-religion').value = data.religion || '';
                            document.getElementById('id_resp-iglesia').value = data.iglesia || '';
                            document.getElementById('id_resp-correo_electronico').value = data.correo_electronico || '';
                            
                            if (data.tiene_whatsapp !== null) {
                                document.getElementById('id_resp-tiene_whatsapp').checked = data.tiene_whatsapp;
                            }
                            
                            // Opcional: Podrías hacer brillar los campos autocompletados
                            // o mostrar un pequeño toast de bootstrap en lugar de un alert
                        }
                    })
                    .catch(error => console.error('Error buscando DPI:', error));
            }
        });
    }
});