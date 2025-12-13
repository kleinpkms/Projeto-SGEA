from django.apps import AppConfig


class CoreConfig(AppConfig):
	default_auto_field = 'django.db.models.BigAutoField'
	name = 'core'

	def ready(self):
		# import signal handlers to ensure they're registered
		try:
			from . import signals  # noqa: F401
		except Exception:
			pass