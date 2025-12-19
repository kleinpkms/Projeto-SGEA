from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from django.test import Client
from core.models import Evento

User = get_user_model()
try:
    u = User.objects.get(username='apitest')
except Exception:
    print('No user apitest')
    raise SystemExit(1)

t = Token.objects.get(user=u)
client = Client()
headers = {'HTTP_AUTHORIZATION': 'Token ' + t.key}

ev = Evento.objects.first()
if not ev:
    print('No events')
    raise SystemExit(1)

for i in range(1,53):
    r = client.post('/api/inscricoes/', {'evento': ev.id}, **headers)
    content = r.content.decode('utf-8')[:200].replace('\n',' ')
    print(f"{i} => {r.status_code} {content}")
