from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import os

User = get_user_model()


def validar_banner(imagem):
	name = getattr(imagem, 'name', '')
	allowed = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.tif')
	if not any(name.lower().endswith(ext) for ext in allowed):
		raise ValidationError('O arquivo deve ser uma imagem (formatos permitidos: PNG, JPG, JPEG, GIF, WEBP, BMP, TIFF).')


class Evento(models.Model):
	nome = models.CharField(max_length=200)
	descricao = models.TextField(blank=True)
	data_inicio = models.DateTimeField()
	data_fim = models.DateTimeField()
	local = models.CharField(max_length=200)
	vagas = models.PositiveIntegerField()
	# duração em minutos (permite durações menores que 1h)
	carga_horaria_minutos = models.PositiveIntegerField(default=240)
	banner = models.ImageField(upload_to='banners/', validators=[validar_banner], blank=True, null=True)
	responsavel = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eventos_criados')
	confirmation_code = models.CharField(max_length=32, blank=True, null=True, unique=True)

	def clean(self):
		from django.utils import timezone as _tz
		from django.utils.timezone import is_naive, make_aware, get_current_timezone
		if self.data_inicio:
			dt = self.data_inicio
			if is_naive(dt):
				dt = make_aware(dt, get_current_timezone())
			# compare in a timezone-aware manner
			now = _tz.now()
			# allow creation for the same minute as 'now' (minute precision)
			now_min = now.replace(second=0, microsecond=0)
			if dt < now_min:
				raise ValidationError('A data de início não pode ser no passado.')
		if not self.responsavel:
			raise ValidationError('Todo evento deve ter um professor responsável.')

	def __str__(self):
		return self.nome

	@property
	def carga_horaria_readable(self):
		m = int(self.carga_horaria_minutos or 0)
		if m >= 60:
			h = m // 60
			rem = m % 60
			h_label = 'hora' if h == 1 else 'horas'
			if rem == 0:
				return f"{h} {h_label}"
			min_label = 'minuto' if rem == 1 else 'minutos'
			return f"{h} {h_label} e {rem} {min_label}"
		# singular/plural for minutes
		min_label = 'minuto' if m == 1 else 'minutos'
		return f"{m} {min_label}"





class Inscricao(models.Model):
	# FK nullable para manter inscrição mesmo se Evento for removido
	evento = models.ForeignKey(Evento, on_delete=models.SET_NULL, null=True, blank=True, related_name='inscricoes')
	participante = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inscricoes')
	data_inscricao = models.DateTimeField(auto_now_add=True)
	# campos opcionais do participante capturados na inscrição
	participante_email = models.EmailField(blank=True, null=True)
	participante_first_name = models.CharField(max_length=150, blank=True, null=True)
	participante_last_name = models.CharField(max_length=150, blank=True, null=True)
	telefone = models.CharField(max_length=30, blank=True, null=True)
	presenca_confirmada = models.BooleanField(default=False)
	certificado_gerado = models.BooleanField(default=False)
	# snapshot do evento para manter certificado válido mesmo após mudanças
	certificado_evento_nome = models.CharField(max_length=200, blank=True, null=True)
	certificado_data_inicio = models.DateTimeField(blank=True, null=True)
	certificado_local = models.CharField(max_length=200, blank=True, null=True)
	certificado_carga_horaria_minutos = models.PositiveIntegerField(blank=True, null=True)
	certificado_emitido_em = models.DateTimeField(blank=True, null=True)

	@property
	def certificado_carga_horaria_readable(self):
		m = int(self.certificado_carga_horaria_minutos or 0)
		if m >= 60:
			h = m // 60
			rem = m % 60
			h_label = 'hora' if h == 1 else 'horas'
			if rem == 0:
				return f"{h} {h_label}"
			min_label = 'minuto' if rem == 1 else 'minutos'
			return f"{h} {h_label} e {rem} {min_label}"
		min_label = 'minuto' if m == 1 else 'minutos'
		return f"{m} {min_label}"

	class Meta:
		unique_together = ('evento', 'participante')

	def clean(self):
		# evita duplicatas (único governador pelo DB também)
		if self.evento and self.evento.inscricoes.filter(participante=self.participante).exclude(pk=self.pk).exists():
			raise ValidationError('Usuário já inscrito neste evento.')
		# verificar vagas
		if self.evento and self.evento.inscricoes.count() >= self.evento.vagas and not self.pk:
			raise ValidationError('Vagas esgotadas para este evento.')

	def __str__(self):
		return f"{self.participante.username} - {self.evento.nome}"



class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    telefone = models.CharField(max_length=30, blank=True, null=True)
    data_nascimento = models.DateField(blank=True, null=True)
    photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return f"Perfil de {self.user.username}"


class EmailVerification(models.Model):
    PURPOSE_CHOICES = [
        ('activate', 'Activate'),
        ('email_change', 'Email change'),
        ('password_change', 'Password change'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=64)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default='activate')
    target_email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.purpose}"

class Auditoria(models.Model):
	usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
	acao = models.CharField(max_length=255)
	data_hora = models.DateTimeField(auto_now_add=True)
	detalhes = models.TextField(blank=True, null=True)

	def __str__(self):
		return f"{self.data_hora} - {self.usuario} - {self.acao}"
