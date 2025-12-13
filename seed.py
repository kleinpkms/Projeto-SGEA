import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.contrib.auth.models import User, Group


def seed():
	grupos = ['Organizador', 'Professor', 'Aluno']
	for g in grupos:
		Group.objects.get_or_create(name=g)

	users = [
		{'username': 'organizador@sgea.com', 'password': 'Admin@123', 'first_name': 'Organizador', 'group': 'Organizador', 'is_staff': True, 'is_superuser': True},
		{'username': 'aluno@sgea.com', 'password': 'Aluno@123', 'first_name': 'Aluno', 'group': 'Aluno', 'is_staff': False, 'is_superuser': False},
		{'username': 'professor@sgea.com', 'password': 'Professor@123', 'first_name': 'Professor', 'group': 'Professor', 'is_staff': True, 'is_superuser': False},
	]

	for u in users:
		user, created = User.objects.get_or_create(username=u['username'], defaults={'first_name': u['first_name'], 'email': u['username']})
		if created:
			user.set_password(u['password'])
			user.is_staff = u['is_staff']
			user.is_superuser = u['is_superuser']
			user.save()
		grp = Group.objects.get(name=u['group'])
		user.groups.add(grp)
		print(f"Usuário {u['username']} garantido.")


if __name__ == '__main__':
	seed()
