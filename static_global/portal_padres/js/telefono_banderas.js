document.addEventListener('DOMContentLoaded', function() {
    const phoneInputs = document.querySelectorAll('.telefono-internacional');
    const itiInstances = [];

    phoneInputs.forEach(function(input) {
        const iti = window.intlTelInput(input, {
            initialCountry: "gt",
            preferredCountries: ["gt", "us", "mx", "sv", "hn"],
            separateDialCode: true, 
            utilsScript: "https://cdn.jsdelivr.net/npm/intl-tel-input@19.2.16/build/js/utils.js",
        });
        itiInstances.push({ input: input, iti: iti });
    });

    // Antes de enviar el formulario, actualizar el valor del input con el número completo
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            itiInstances.forEach(function(instance) {
                if (instance.input.value) {
                    // iti.getNumber() obtiene el formato E.164 (ej. +50212345678)
                    instance.input.value = instance.iti.getNumber(); 
                }
            });
        });
    });
});