import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Inscricao
User = get_user_model()

removed = 0
# delete inscricoes with test event name '32323'
q1 = Inscricao.objects.filter(certificado_evento_nome='32323')
removed += q1.count()
q1.delete()
# delete inscricoes by test users
for uname in ('aluno@sgea.com','organizador@sgea.com'):
    u = User.objects.filter(username=uname).first()
    if u:
        q = Inscricao.objects.filter(participante=u)
        removed += q.count()
        q.delete()

print('Removidas', removed, 'inscricoes de teste')
