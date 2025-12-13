from django.contrib.auth import get_user_model
from core.models import Evento, Inscricao
User = get_user_model()

u = User.objects.filter(username='aluno@sgea.com').first()
e = Evento.objects.first()
print('user=', u, 'event=', e)
if u and e:
    ins = Inscricao.objects.create(participante=u, evento=e)
    print('created', ins.id)
else:
    print('missing user or event; cannot create')
