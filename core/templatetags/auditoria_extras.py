from django import template
import os

register = template.Library()


@register.filter(name='basename')
def basename(value):
    """Return the basename of a path or URL-like string."""
    try:
        if not value:
            return ''
        # if it looks like a URL, split on '/' and take last
        if '/' in value:
            return value.rstrip('/').split('/')[-1]
        return os.path.basename(value)
    except Exception:
        return value
