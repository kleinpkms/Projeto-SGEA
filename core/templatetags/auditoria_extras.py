from django import template
import os

register = template.Library()


@register.filter(name='basename')
def basename(value):
    """Retorna o nome do arquivo de um path ou URL."""
    try:
        if not value:
            return ''
        # se parece URL, pega a última parte
        if '/' in value:
            return value.rstrip('/').split('/')[-1]
        return os.path.basename(value)
    except Exception:
        return value
