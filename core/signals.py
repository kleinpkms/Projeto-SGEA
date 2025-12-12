from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import Evento, Auditoria

@receiver(post_save, sender=User)
def enviar_email_boas_vindas(sender, instance, created, **kwargs):
    if created:
        Auditoria.objects.create(
            usuario=instance, 
            acao="Criação de Usuário", 
            detalhes=f"Novo usuário cadastrado: {instance.username}"
        )
        
        assunto = 'Bem-vindo ao SGEA!'
        mensagem = f"Olá, {instance.username}! Bem-vindo ao SGEA."
        print(f"--- SIMULANDO ENVIO DE E-MAIL PARA {instance.email} ---")
        send_mail(assunto, mensagem, settings.EMAIL_HOST_USER, [instance.email], fail_silently=False)

@receiver(post_save, sender=Evento)
def log_evento_save(sender, instance, created, **kwargs):
    acao = "Cadastro de Evento" if created else "Alteração de Evento"
    user_responsavel = instance.responsavel
    
    Auditoria.objects.create(
        usuario=user_responsavel,
        acao=acao,
        detalhes=f"Evento: {instance.nome} | Local: {instance.local}"
    )

@receiver(post_delete, sender=Evento)
def log_evento_delete(sender, instance, **kwargs):
    Auditoria.objects.create(
        usuario=instance.responsavel,
        acao="Exclusão de Evento",
        detalhes=f"O evento '{instance.nome}' foi removido."
    )