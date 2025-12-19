from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from .models import Evento, Inscricao


class EventoSerializer(serializers.ModelSerializer):
	organizador = serializers.CharField(source='responsavel.username', read_only=True)
	inscricoes_count = serializers.IntegerField(read_only=True)
	carga_horaria_minutos = serializers.IntegerField(read_only=True)
	carga_horaria = serializers.SerializerMethodField(read_only=True)

	class Meta:
		model = Evento
		fields = ['id', 'nome', 'descricao', 'data_inicio', 'data_fim', 'local', 'vagas', 'banner', 'organizador', 'inscricoes_count', 'carga_horaria_minutos', 'carga_horaria']

	def get_carga_horaria(self, obj):
		return getattr(obj, 'carga_horaria_readable', None)


class InscricaoSerializer(serializers.ModelSerializer):
	class Meta:
		model = Inscricao
		fields = ['id', 'evento']

	def create(self, validated_data):
		request = self.context.get('request')
		user = request.user

		# Organizadores não podem se inscrever nos eventos
		if user.groups.filter(name='Organizador').exists():
			raise PermissionDenied('Organizadores não podem se inscrever em eventos.')
		evento = validated_data.get('evento')
		inscricao = Inscricao(participante=user, evento=evento)

		# salva dados do evento para o certificado sobreviver a mudanças/deleção
		if evento:
			inscricao.certificado_evento_nome = evento.nome
			inscricao.certificado_data_inicio = evento.data_inicio
			inscricao.certificado_local = evento.local
			inscricao.certificado_carga_horaria_minutos = evento.carga_horaria_minutos

		# preenche contato do participante a partir do perfil quando disponível
		profile = getattr(user, 'profile', None)
		inscricao.participante_email = (profile and profile.user.email) or user.email
		inscricao.participante_first_name = (profile and user.first_name) or user.first_name
		inscricao.participante_last_name = (profile and user.last_name) or user.last_name
		inscricao.telefone = (profile and profile.telefone) or None
		inscricao.clean()
		# NÃO gera certificado na inscrição; só ao confirmar presença ou código
		inscricao.save()
		return inscricao

	def get_carga_horaria(self, obj):
		# não usado aqui, mas mantido por completude
		return getattr(obj.evento, 'carga_horaria_readable', None)
