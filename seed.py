import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.contrib.auth.models import User, Group

def seed():
    print("Iniciando a carga de dados (Seeding)...")

    grupos = ['Organizador', 'Professor', 'Aluno']
    for nome_grupo in grupos:
        Group.objects.get_or_create(name=nome_grupo)
        print(f"Grupo '{nome_grupo}' garantido.")

    usuarios = [
        {
            "nome": "Organizador",
            "login": "organizador@sgea.com",
            "senha": "Admin@123",
            "grupo": "Organizador",
            "is_superuser": True,
            "is_staff": True
        },
        {
            "nome": "Aluno",
            "login": "aluno@sgea.com",
            "senha": "Aluno@123",
            "grupo": "Aluno",
            "is_superuser": False,
            "is_staff": False
        },
        {
            "nome": "Professor",
            "login": "professor@sgea.com",
            "senha": "Professor@123",
            "grupo": "Professor",
            "is_superuser": False,
            "is_staff": False
        }
    ]

    for u in usuarios:
        if not User.objects.filter(username=u['login']).exists():
            usuario = User.objects.create_user(
                username=u['login'],
                email=u['login'],
                password=u['senha']
            )
            usuario.first_name = u['nome']
            usuario.is_superuser = u['is_superuser']
            usuario.is_staff = u['is_staff'] 
            usuario.save()
            
            grupo = Group.objects.get(name=u['grupo'])
            usuario.groups.add(grupo)
            
            print(f"Usuário '{u['login']}' criado com sucesso.")
        else:
            print(f"Usuário '{u['login']}' já existe.")

    print("--- Carga de dados concluída! ---")

if __name__ == '__main__':
    seed()