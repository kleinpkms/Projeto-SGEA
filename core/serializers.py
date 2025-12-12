from rest_framework import serializers
from .models import Evento, Inscricao

class EventoSerializer(serializers.ModelSerializer):
    organizador = serializers.CharField(source='responsavel.username', read_only=True)

    class Meta:
        model = Evento
        fields = ['id', 'nome', 'descricao', 'data_inicio', 'local', 'vagas', 'banner', 'organizador']

class InscricaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inscricao
        fields = ['id', 'evento']
    
    def create(self, validated_data):
        user = self.context['request'].user
        inscricao = Inscricao.objects.create(participante=user, **validated_data)
        return inscricao