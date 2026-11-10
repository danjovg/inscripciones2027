from django_hosts import patterns, host

host_patterns = patterns('',
    host(r'inscripciones', 'portal_padres.urls', name='padres'),
    host(r'docentes', 'portal_docentes.urls', name='docentes'),
    host(r'gestion', 'portal_staff.urls', name='staff'),
)