from django.apps import AppConfig


class CoreConfig(AppConfig):
	default_auto_field = 'django.db.models.BigAutoField'
	name = 'core'

	def ready(self):
		# importa signals para registrá-los
		try:
			from . import signals  # noqa: F401
		except Exception:
			pass
