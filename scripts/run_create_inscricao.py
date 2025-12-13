import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Evento, Inscricao
User = get_user_model()

u = User.objects.filter(username='aluno@sgea.com').first()
e = Evento.objects.first()
print('user=', u, 'event=', e)
if u and e:
    try:
        ins = Inscricao.objects.create(participante=u, evento=e)
        print('created', ins.id)
    except Exception as ex:
        print('creation failed:', ex)
else:
    print('missing user or event; cannot create')
