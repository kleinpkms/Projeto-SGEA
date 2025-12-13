from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Optionally load environment variables from a local .env file for development.
# Use importlib.import_module to avoid static imports that some linters complain about
try:
	import importlib
	dotenv = importlib.import_module('dotenv')
	if hasattr(dotenv, 'load_dotenv'):
		dotenv.load_dotenv(os.path.join(BASE_DIR, '.env'))
except Exception:
	# python-dotenv not installed or .env missing — fall back to os.environ
	pass
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-recreated-for-local-development'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']


# Application definition

INSTALLED_APPS = [
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'rest_framework',
	'rest_framework.authtoken',
	'core',
]

MIDDLEWARE = [
	'django.middleware.security.SecurityMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'setup.urls'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [
			os.path.join(BASE_DIR, 'core', 'templates'),
			# Também procurar diretamente na subpasta 'core' dentro de templates,
			# útil quando o projeto é executado de uma pasta diferente.
			os.path.join(BASE_DIR, 'core', 'templates', 'core'),
		],
		'APP_DIRS': True,
		'OPTIONS': {
			'context_processors': [
				'django.template.context_processors.debug',
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
			],
		},
	},
]

WSGI_APPLICATION = 'setup.wsgi.application'


# Database
# Using SQLite for local development
DATABASES = {
	'default': {
		'ENGINE': 'django.db.backends.sqlite3',
		'NAME': BASE_DIR / 'db.sqlite3',
	}
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
	{
		'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
		'OPTIONS': {'min_length': 8}
	},
	{
		'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
	},
]


# Internationalization
LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


REST_FRAMEWORK = {
	'DEFAULT_AUTHENTICATION_CLASSES': [
		'rest_framework.authentication.TokenAuthentication',
		'rest_framework.authentication.SessionAuthentication',
	],
	'DEFAULT_PERMISSION_CLASSES': [
		'rest_framework.permissions.IsAuthenticated',
	],
	'DEFAULT_THROTTLE_CLASSES': [
		'rest_framework.throttling.ScopedRateThrottle',
	],
	'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
	'PAGE_SIZE': 6,
	'DEFAULT_THROTTLE_RATES': {
		'user': '1000/day',
		'event-list': '20/day',
		'inscricao': '50/day',
	}
}


# Email configuration: prefer SMTP when environment variables are provided,
# otherwise fall back to console backend for local development.
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'sgea25verify@gmail.com')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') in ('1', 'true', 'True')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'zeyg ftvh wead pkbo')

# If an SMTP password is provided via environment, use SMTP backend;
# otherwise default to console backend for local development so emails
# are printed to the console and won't fail silently due to missing creds.
if EMAIL_HOST_PASSWORD:
	EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
	EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Default From email used when sending messages
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# login URL for decorators
LOGIN_URL = '/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
