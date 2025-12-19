from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventoViewSet, InscricaoViewSet, emitir_certificado_view, api_login, sair, login_view, home, admin_area, admin_event_inscritos, cancelar_inscricao, admin_auditoria, admin_clear_auditoria, download_auditoria_backup, admin_api_overview, admin_api_audits, api_cancel_inscricao, api_confirm_inscricao, api_generate_code, api_cancel_inscricao_as, api_confirm_inscricao_as, api_create_inscricao_as, api_list_event_inscricoes
from .views import cancelar_minha_inscricao, confirmar_presenca, generate_confirmation_code, confirmar_codigo_participante
from .views import register_view, verify_view, profile_view, change_password_view
from .views import resend_verification

router = DefaultRouter()
router.register(r'eventos', EventoViewSet, basename='eventos')
router.register(r'inscricoes', InscricaoViewSet, basename='inscricoes')

urlpatterns = [
	path('api-token-auth/', api_login, name='api_login'),
	path('api/', include(router.urls)),
	path('admin-api/', admin_api_overview, name='admin_api_overview'),
	path('admin-api/audits/', admin_api_audits, name='admin_api_audits'),
	# APIs internas para admin/testes (casam com UI admin)
	path('api/internal/inscricoes/<int:insc_id>/cancel/', api_cancel_inscricao, name='api_cancel_inscricao'),
	path('api/internal/inscricoes/<int:insc_id>/confirm/', api_confirm_inscricao, name='api_confirm_inscricao'),
	path('api/internal/eventos/<int:event_id>/generate-code/', api_generate_code, name='api_generate_code'),
	path('api/internal/inscricoes/<int:insc_id>/cancel-as/', api_cancel_inscricao_as, name='api_cancel_inscricao_as'),
	path('api/internal/inscricoes/<int:insc_id>/confirm-as/', api_confirm_inscricao_as, name='api_confirm_inscricao_as'),
	path('api/internal/inscricoes/create-as/', api_create_inscricao_as, name='api_create_inscricao_as'),
	# endpoints que aceitam evento_id + target_user_id + as_user_id no JSON
	path('api/internal/inscricoes/cancel-by/', api_cancel_inscricao_as, name='api_cancel_inscricao_by'),
	path('api/internal/inscricoes/confirm-by/', api_confirm_inscricao_as, name='api_confirm_inscricao_by'),
	path('api/internal/eventos/<int:event_id>/inscricoes/', api_list_event_inscricoes, name='api_list_event_inscricoes'),
	path('certificado/<int:inscricao_id>/', emitir_certificado_view, name='baixar_certificado'),
	path('sair/', sair, name='sair'),
	path('admin-area/', admin_area, name='admin_area'),
	path('admin-area/inscritos/<int:event_id>/', admin_event_inscritos, name='admin_event_inscritos'),
	path('admin-area/auditoria/', admin_auditoria, name='admin_auditoria'),
    path('admin-area/auditoria/clear/', admin_clear_auditoria, name='admin_auditoria_clear'),
		path('admin-area/auditoria/backup/<str:filename>/', download_auditoria_backup, name='admin_auditoria_backup'),
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
