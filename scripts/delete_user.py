#!/usr/bin/env python3
import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
sys.path.insert(0, str(BASE_DIR))

django.setup()

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.conf import settings
from django.db import transaction

User = get_user_model()
email = 'marcelo3rbangelini.wrk@gmail.com'

with transaction.atomic():
    users = User.objects.filter(email__iexact=email)
    if not users.exists():
        print('Usuário não encontrado:', email)
        sys.exit(0)
    for u in users:
        print(f"Removendo usuário: id={u.id} username={u.username} email={u.email}")
        # tokens
        try:
            from rest_framework.authtoken.models import Token
            tcount = Token.objects.filter(user=u).count()
            if tcount:
                Token.objects.filter(user=u).delete()
                print(f"  Deletados {tcount} token(s)")
        except Exception:
            pass
        # email verifications
        try:
            from core.models import EmailVerification, Evento, Inscricao, UserProfile
            ev_count = EmailVerification.objects.filter(user=u).count()
            if ev_count:
                EmailVerification.objects.filter(user=u).delete()
                print(f"  Deletados {ev_count} EmailVerification(s)")
        except Exception:
            pass
        # delete profile photo
        try:
            profile = getattr(u, 'profile', None)
            if profile and profile.photo:
                try:
                    ppath = profile.photo.path
                    if ppath and default_storage.exists(ppath):
                        default_storage.delete(ppath)
                        print(f"  Arquivo de foto do perfil removido: {ppath}")
                except Exception as e:
                    print('  Não foi possível remover foto do perfil:', e)
        except Exception:
            pass
        # delete events created by user (also try to remove banners)
        try:
            ev_qs = Evento.objects.filter(responsavel=u)
            ev_count = ev_qs.count()
            if ev_count:
                for ev in ev_qs:
                    try:
                        if ev.banner and getattr(ev.banner, 'path', None) and default_storage.exists(ev.banner.path):
                            default_storage.delete(ev.banner.path)
                            print(f"  Banner removido: {ev.banner.path}")
                    except Exception:
                        pass
                ev_qs.delete()
                print(f"  Deletados {ev_count} Evento(s) criados pelo usuário")
        except Exception:
            pass
        # delete inscricoes where participant is this user
        try:
            ins_count = Inscricao.objects.filter(participante=u).count()
            if ins_count:
                Inscricao.objects.filter(participante=u).delete()
                print(f"  Deletadas {ins_count} Inscricao(ões) do usuário")
        except Exception:
            pass
        # finally delete the user (will cascade as configured)
        try:
            u.delete()
            print('  Usuário removido com sucesso (delete() executado).')
        except Exception as e:
            print('  Erro ao deletar usuário:', e)

print('Operação concluída.')
