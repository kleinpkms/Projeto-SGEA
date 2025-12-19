import json
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from django.test import Client
from core.models import Evento

User = get_user_model()
admin = User.objects.get(username='apitest')
admin_token = Token.objects.get(user=admin).key
client = Client()
headers = {'HTTP_AUTHORIZATION': 'Token ' + admin_token}

# ensure target student
student, created = User.objects.get_or_create(username='student1', defaults={'email':'student1@example.com'})
if created:
    student.set_password('studpass')
    student.save()

# pick event
ev = Evento.objects.first()
print('EVENT', ev.id if ev else None)

# create inscription as student
body = json.dumps({'evento': ev.id, 'user_id': student.id})
resp = client.post('/api/internal/inscricoes/create-as/', data=body, content_type='application/json', **headers)
print('create-as', resp.status_code, resp.content.decode('utf-8'))

# list inscriptions for event
resp = client.get(f'/api/internal/eventos/{ev.id}/inscricoes/', **{'HTTP_AUTHORIZATION': 'Token '+admin_token})
print('list-event-inscricoes', resp.status_code, resp.content.decode('utf-8')[:500])

# cancel-by
body = json.dumps({'evento_id': ev.id, 'target_user_id': student.id, 'as_user_id': student.id})
resp = client.post('/api/internal/inscricoes/cancel-by/', data=body, content_type='application/json', **headers)
print('cancel-by', resp.status_code, resp.content.decode('utf-8'))

# recreate inscription to test confirm
body = json.dumps({'evento': ev.id, 'user_id': student.id})
resp = client.post('/api/internal/inscricoes/create-as/', data=body, content_type='application/json', **headers)
print('recreate-as', resp.status_code, resp.content.decode('utf-8'))

# confirm-by
body = json.dumps({'evento_id': ev.id, 'target_user_id': student.id, 'as_user_id': admin.id})
resp = client.post('/api/internal/inscricoes/confirm-by/', data=body, content_type='application/json', **headers)
print('confirm-by', resp.status_code, resp.content.decode('utf-8'))
