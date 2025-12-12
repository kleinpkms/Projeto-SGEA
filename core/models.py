from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

def validar_banner(imagem):
    if not imagem.name.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise ValidationError("O arquivo deve ser uma imagem (PNG, JPG, JPEG).")

class Evento(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField()
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField()
    local = models.CharField(max_length=200)
    vagas = models.PositiveIntegerField()
    banner = models.ImageField(upload_to='banners/', validators=[validar_banner], blank=True, null=True)
    responsavel = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eventos_criados')

    def clean(self):
        if self.data_inicio and self.data_inicio < timezone.now():
            raise ValidationError('A data de início não pode ser no passado.')

    def __str__(self):
        return self.nome

class Inscricao(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    participante = models.ForeignKey(User, on_delete=models.CASCADE)
    data_inscricao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('evento', 'participante')
        verbose_name = "Inscrição"        
        verbose_name_plural = "Inscrições" 

    def __str__(self):
        return f"{self.participante.username} - {self.evento.nome}"


class Auditoria(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.CharField(max_length=255) 
    data_hora = models.DateTimeField(auto_now_add=True)
    detalhes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.usuario} - {self.acao} em {self.data_hora}"