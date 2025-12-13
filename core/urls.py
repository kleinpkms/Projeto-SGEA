from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventoViewSet, InscricaoViewSet, emitir_certificado_view, api_login, sair, login_view, home, admin_area, admin_event_inscritos, cancelar_inscricao
from .views import cancelar_minha_inscricao, confirmar_presenca, generate_confirmation_code, confirmar_codigo_participante
from .views import register_view, verify_view, profile_view, change_password_view
from .views import resend_verification

router = DefaultRouter()
router.register(r'eventos', EventoViewSet, basename='eventos')
router.register(r'inscricoes', InscricaoViewSet, basename='inscricoes')

urlpatterns = [
	path('api-token-auth/', api_login, name='api_login'),
	path('api/', include(router.urls)),
	path('certificado/<int:inscricao_id>/', emitir_certificado_view, name='baixar_certificado'),
	path('sair/', sair, name='sair'),
	path('admin-area/', admin_area, name='admin_area'),
	path('admin-area/inscritos/<int:event_id>/', admin_event_inscritos, name='admin_event_inscritos'),
	path('admin-area/cancelar-inscricao/', cancelar_inscricao, name='cancelar_inscricao'),
	path('admin-area/confirmar-presenca/', confirmar_presenca, name='confirmar_presenca'),
	path('admin-area/generate-code/<int:event_id>/', generate_confirmation_code, name='generate_confirmation_code'),
	path('inscricao/confirmar/<int:inscricao_id>/', confirmar_codigo_participante, name='confirmar_codigo_participante'),
	path('inscricao/cancelar/', cancelar_minha_inscricao, name='cancelar_minha_inscricao'),
	path('login/', login_view, name='login'),
		path('register/', register_view, name='register'),
		path('verify/<int:verification_id>/', verify_view, name='verify'),
		path('verify/resend/<int:verification_id>/', resend_verification, name='resend_verification'),
		path('perfil/', profile_view, name='perfil'),
		path('perfil/alterar-senha/', change_password_view, name='alterar_senha'),
	path('home/', home, name='home'),
	path('', login_view),
]
