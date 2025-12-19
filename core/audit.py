from django.db import DatabaseError
from .models import Auditoria

def log_audit(usuario=None, acao='', detalhes=''):
    """Registra um `Auditoria` com segurança; ignora erros de BD."""
    try:
        Auditoria.objects.create(usuario=usuario, acao=acao, detalhes=detalhes)
    except DatabaseError:
        # evita crash se BD indisponível durante migrações
        pass

