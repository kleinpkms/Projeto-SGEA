from django.db import DatabaseError
from .models import Auditoria

def log_audit(usuario=None, acao='', detalhes=''):
    """Safely create an Auditoria record. Swallows DB errors (useful during initial migrations)."""
    try:
        Auditoria.objects.create(usuario=usuario, acao=acao, detalhes=detalhes)
    except DatabaseError:
        # during migrations or if DB missing, avoid crashing the app
        pass
