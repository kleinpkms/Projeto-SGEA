from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseForbidden
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.throttling import UserRateThrottle
from .models import Evento, Inscricao, Auditoria
from .serializers import EventoSerializer, InscricaoSerializer
from django.contrib.auth.decorators import login_required


class EventoRateThrottle(UserRateThrottle):
    rate = '20/day'

class InscricaoRateThrottle(UserRateThrottle):
    rate = '50/day'

class EventoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Evento.objects.all()
    serializer_class = EventoSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [EventoRateThrottle]

    def list(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            Auditoria.objects.create(
                usuario=request.user,
                acao="Consulta API",
                detalhes="Usuário solicitou a lista de eventos via API."
            )
        return super().list(request, *args, **kwargs)

class InscricaoViewSet(viewsets.ModelViewSet):
    queryset = Inscricao.objects.all()
    serializer_class = InscricaoSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [InscricaoRateThrottle]
    http_method_names = ['post', 'get']

    def get_queryset(self):
        return Inscricao.objects.filter(participante=self.request.user)


def emitir_certificado(request, inscricao_id):
    inscricao = get_object_or_404(Inscricao, id=inscricao_id)
    
    if inscricao.participante != request.user:
        return HttpResponseForbidden("Você não tem permissão para ver este certificado.")

    if inscricao.evento.data_fim > timezone.now():
        return HttpResponseForbidden("O certificado só estará disponível após o término do evento.")

    if not inscricao.presenca_confirmada:
        return HttpResponseForbidden("Sua presença neste evento ainda não foi confirmada.")

    Auditoria.objects.create(
        usuario=request.user,
        acao="Emissão de Certificado",
        detalhes=f"Certificado gerado para o evento: {inscricao.evento.nome}"
    )

    return render(request, 'core/certificado.html', {
        'inscricao': inscricao,
        'data_atual': timezone.now()
    })

def home(request):
    inscricoes = []
    if request.user.is_authenticated:
        inscricoes = Inscricao.objects.filter(participante=request.user)
    
    return render(request, 'core/index.html', {'inscricoes': inscricoes})

from django.contrib.auth.decorators import login_required

def home(request):
    inscricoes = []
    if request.user.is_authenticated:
        inscricoes = Inscricao.objects.filter(participante=request.user)
    
    return render(request, 'core/index.html', {'inscricoes': inscricoes})