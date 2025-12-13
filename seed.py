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
			user.is_active = True
			user.save()
		# ensure group
		grp = Group.objects.get(name=u['group'])
		user.groups.add(grp)
		# ensure profile exists with realistic fields and surname set to id
		try:
			from core.models import UserProfile
			# set last_name to user id for uniqueness as requested
			user.last_name = str(user.id)
			user.save()
			# create profile with randomized phone and dob
			import random
			d = random.randint(1,28)
			m = random.randint(1,12)
			y = random.randint(1980,2002)
			telefone = f"(1{random.randint(0,9)}) 9{random.randint(10000,99999)}-{random.randint(1000,9999)}"
			profile, pcreated = UserProfile.objects.get_or_create(user=user, defaults={'telefone': telefone})
			if pcreated:
				try:
					from django.utils import timezone
					profile.data_nascimento = timezone.datetime(y, m, d).date()
					profile.save()
				except Exception:
					pass
		except Exception:
			pass
		print(f"Usuário {u['username']} garantido com perfil.")


if __name__ == '__main__':
	seed()
