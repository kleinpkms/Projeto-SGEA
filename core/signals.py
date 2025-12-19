from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .models import Auditoria
from .audit import log_audit

User = get_user_model()


@receiver(post_save, sender=User)
def enviar_email_boas_vindas(sender, instance, created, **kwargs):
	if created:
		# registra criação no log (não enviar e-mail aqui — espera verificação)
		log_audit(usuario=instance, acao='Criação de Usuário', detalhes=f'Novo usuário: {instance.username}')



@receiver(pre_delete, sender=None)
def snapshot_inscricoes_before_event_delete(sender, instance, **kwargs):
	# Ao deletar um Evento, preserva snapshot dos dados nas inscrições
	try:
		from .models import Evento, Inscricao
	except Exception:
		return
	# only act for Evento deletions
	if not isinstance(instance, Evento):
		return
	ev = instance
	inscricoes = Inscricao.objects.filter(evento=ev)
	for ins in inscricoes:
		changed = False
		if not ins.certificado_evento_nome:
			ins.certificado_evento_nome = ev.nome
			changed = True
		if not ins.certificado_data_inicio:
			ins.certificado_data_inicio = ev.data_inicio
			changed = True
		if not ins.certificado_local:
			ins.certificado_local = ev.local
			changed = True
		if not ins.certificado_carga_horaria_minutos and ev.carga_horaria_minutos:
			ins.certificado_carga_horaria_minutos = ev.carga_horaria_minutos
			changed = True
		if changed:
			ins.save()
			# remove registro de certificado para não listar participante em evento removido
		try:
			if ins.certificado_gerado:
				ins.certificado_gerado = False
				ins.certificado_emitido_em = None
				ins.save()
			elif not ins.certificado_gerado:
				# ensure not registered
				ins.certificado_emitido_em = None
				ins.save()
		except Exception:
			# be defensive in signal handler
			pass
