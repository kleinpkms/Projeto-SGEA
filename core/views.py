
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_datetime
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponseForbidden, JsonResponse, FileResponse, Http404
from django.utils import timezone
import logging
import json
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, ScopedRateThrottle
from rest_framework.authtoken.models import Token
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from .models import Evento, Inscricao, Auditoria
from django.db.models import Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .serializers import EventoSerializer, InscricaoSerializer
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone as dj_timezone
from django.utils.timezone import make_aware, get_current_timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.cache import never_cache
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import os
from django.contrib.sites.shortcuts import get_current_site
from django.templatetags.static import static
import secrets, string
from datetime import timedelta
from django.utils import timezone as dj_tz
from .audit import log_audit

User = get_user_model()


class EventoRateThrottle(UserRateThrottle):
    scope = 'event-list'


class InscricaoRateThrottle(UserRateThrottle):
    scope = 'inscricao'


class EventoViewSet(viewsets.ReadOnlyModelViewSet):
    # adiciona contagem de inscrições aos eventos para uso do serializer/UI
    queryset = Evento.objects.all().annotate(inscricoes_count=Count('inscricoes'))
    serializer_class = EventoSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'event-list'

    def list(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            log_audit(request.user, 'Consulta API', 'Listou eventos via API')
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        # registra acesso a evento via API
        if request.user.is_authenticated:
            pk = kwargs.get('pk') or (args[0] if args else None)
            try:
                log_audit(request.user, 'Consulta API', f'Requisitou evento id={pk}')
            except Exception:
                pass
        return super().retrieve(request, *args, **kwargs)


class InscricaoViewSet(viewsets.ModelViewSet):
    queryset = Inscricao.objects.all()
    serializer_class = InscricaoSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'inscricao'
    http_method_names = ['post', 'get']

    def get_queryset(self):
        return Inscricao.objects.filter(participante=self.request.user)

    def list(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                log_audit(request.user, 'Consulta API', 'Listou inscrições via API')
            except Exception:
                pass
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        # evita inscrições em eventos já iniciados/finalizados e mostra erro claro
        # pega id do evento dos dados da requisição (se houver)
        evento_id = None
        if isinstance(request.data, dict):
            evento_id = request.data.get('evento')
        else:
            evento_id = request.POST.get('evento')
        # organizador não pode se inscrever: checa permissão primeiro
        if request.user.groups.filter(name='Organizador').exists():
            accept = request.META.get('HTTP_ACCEPT', '')
            msg = 'Você faz parte do grupo Organizador e não pode se inscrever em eventos. Use uma conta de Aluno/Professor ou entre em contato com o administrador.'
            if 'text/html' in accept:
                # retorna página simples com alerta e volta
                from django.http import HttpResponse
                safe_msg = json.dumps(msg)
                html = '<html><head><meta charset="utf-8"><title>Acesso negado</title></head><body><script>try{alert(' + safe_msg + ');}catch(e){};try{window.history.back();}catch(e){window.location.href="/home/";}</script></body></html>'
                return HttpResponse(html, status=403)
            return Response({'detail': msg}, status=status.HTTP_403_FORBIDDEN)

        # verifica datas antes de criar
        if evento_id:
            evento = Evento.objects.filter(id=evento_id).first()
            if evento:
                now = timezone.now()
                # evento finalizado
                if evento.data_fim and evento.data_fim <= now:
                    accept = request.META.get('HTTP_ACCEPT', '')
                    msg = 'O evento já terminou e não é mais possível se inscrever.'
                    if 'text/html' in accept:
                        from django.http import HttpResponse
                        html = f"""<html><head><meta charset='utf-8'><title>Não é possível inscrever</title></head><body>
                        <div style='position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.45)'>
                          <div style='background:#fff;padding:18px;border-radius:10px;max-width:520px;'>
                            <div style='font-weight:700;margin-bottom:12px;'>Aviso</div>
                            <div style='margin-bottom:12px;'>{msg}</div>
                            <div style='text-align:right;'><button onclick="window.history.back();" style='padding:8px 12px;border-radius:6px;border:none;background:#007acc;color:#fff;cursor:pointer;'>Voltar</button></div>
                          </div>
                        </div></body></html>"""
                        return HttpResponse(html, status=400)
                    return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
                # evento em andamento
                if evento.data_inicio and evento.data_inicio <= now < evento.data_fim:
                    accept = request.META.get('HTTP_ACCEPT', '')
                    msg = 'O evento já começou e não é possível se inscrever enquanto está em andamento.'
                    if 'text/html' in accept:
                        from django.http import HttpResponse
                        html = f"""<html><head><meta charset='utf-8'><title>Não é possível inscrever</title></head><body>
                        <div style='position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.45)'>
                          <div style='background:#fff;padding:18px;border-radius:10px;max-width:520px;'>
                            <div style='font-weight:700;margin-bottom:12px;'>Aviso</div>
                            <div style='margin-bottom:12px;'>{msg}</div>
                            <div style='text-align:right;'><button onclick="window.history.back();" style='padding:8px 12px;border-radius:6px;border:none;background:#007acc;color:#fff;cursor:pointer;'>Voltar</button></div>
                          </div>
                        </div></body></html>"""
                        return HttpResponse(html, status=400)
                    return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resp = super().create(request, *args, **kwargs)
            # se inscrição criada, registra auditoria
            try:
                if hasattr(resp, 'status_code') and resp.status_code in (200, 201):
                    # tenta extrair id criado e evento
                    insc_id = None
                    if isinstance(resp.data, dict):
                        insc_id = resp.data.get('id') or resp.data.get('pk')
                    # evento_id já extraído dos dados
                    # inclui nome do evento quando houver
                    try:
                        ev_obj = Evento.objects.filter(id=evento_id).first()
                        ev_name = ev_obj.nome if ev_obj else ''
                    except Exception:
                        ev_name = ''
                    log_audit(request.user, 'Inscrição criada', f'Inscrição id={insc_id} evento_id={evento_id} evento_name="{ev_name}"')
            except Exception:
                pass
            return resp
        except Exception as e:
            # Se o serializer levantou erro de permissão, retorna mensagem amigável
            from rest_framework.exceptions import PermissionDenied as DRFPerm
            if isinstance(e, DRFPerm) or (hasattr(e, 'detail') and 'Organizador' in str(e)):
                accept = request.META.get('HTTP_ACCEPT', '')
                msg = 'Você faz parte do grupo Organizador e não pode se inscrever em eventos. Use uma conta de Aluno/Professor ou entre em contato com o administrador.'
                if 'text/html' in accept:
                    safe_msg = json.dumps(msg)
                    html = '<html><head><meta charset="utf-8"><title>Acesso negado</title></head><body><script>try{alert(' + safe_msg + ');}catch(e){};try{window.history.back();}catch(e){window.location.href="/home/";}</script></body></html>'
                    from django.http import HttpResponse
                    return HttpResponse(html, status=403)
                return Response({'detail': msg}, status=status.HTTP_403_FORBIDDEN)
            # erro inesperado: retorna JSON 500 genérico
            return Response({'error': str(e)}, status=500)


@login_required
def emitir_certificado_view(request, inscricao_id):
    inscricao = get_object_or_404(Inscricao, id=inscricao_id)
    # só mostra se certificado existir
    if not inscricao.certificado_gerado:
        return HttpResponseForbidden('Certificado ainda não disponível.')
    # registra visualização/download do certificado
    try:
        usuario = request.user if request.user.is_authenticated else None
        try:
            participante_name = (inscricao.participante.get_full_name() or inscricao.participante.username) if inscricao.participante else None
        except Exception:
            participante_name = None
        log_audit(usuario, 'Visualizou/Baixou certificado', f'Inscrição id={inscricao.id} participante_id={inscricao.participante_id} participante_name="{participante_name}"')
    except Exception:
        pass
    return render(request, 'core/certificado.html', {'inscricao': inscricao, 'data_atual': timezone.now()})


@never_cache
def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    inscricoes = Inscricao.objects.filter(participante=request.user)
    eventos_qs = Evento.objects.all().annotate(inscricoes_count=Count('inscricoes')).order_by('data_inicio')
    inscricao_event_ids = list(inscricoes.values_list('evento_id', flat=True))

    # paginação no servidor (param page via GET)
    page_num = request.GET.get('page', 1)
    paginator = Paginator(eventos_qs, 6)  # 6 per page to match API PAGE_SIZE
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    feed_events = []
    for evento in page_obj.object_list:
        inscritos_count = getattr(evento, 'inscricoes_count', None)
        if inscritos_count is None:
            inscritos_count = evento.inscricoes.count()
        remaining = max(0, evento.vagas - inscritos_count)
        is_inscrito = evento.id in inscricao_event_ids
        feed_events.append({'evento': evento, 'remaining': remaining, 'is_inscrito': is_inscrito})
    response = render(request, 'core/index.html', {
        'inscricoes': inscricoes,
        'feed_events': feed_events,
        'page_obj': page_obj,
        'show_admin': request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=['Professor', 'Organizador']).exists()),
        'user_inscricoes_event_ids': list(inscricoes.values_list('evento_id', flat=True)),
        'is_organizador': request.user.groups.filter(name='Organizador').exists(),
        'now': timezone.now(),
    })
    # evita cache da página autenticada
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


def sair(request):
    try:
        user = request.user if request.user.is_authenticated else None
        log_audit(user, 'Logout', f'Usuário efetuou logout')
    except Exception:
        pass
    logout(request)
    return redirect('login')


@login_required
def admin_area(request):
    # se usuário não tem acesso admin, mostra aviso com botão voltar
    if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=['Professor', 'Organizador']).exists()):
        return render(request, 'core/admin_no_access.html', {})
    # área admin simples com estatísticas rápidas
    # Professores veem só eventos que criaram
    if request.user.groups.filter(name='Professor').exists():
        recent_events = Evento.objects.filter(responsavel=request.user).order_by('-data_inicio')[:12]
        total_eventos = Evento.objects.filter(responsavel=request.user).count()
        # Professores veem inscrições só dos seus eventos
        total_inscricoes = Inscricao.objects.filter(evento__responsavel=request.user).count()
    else:
        recent_events = Evento.objects.all().order_by('-data_inicio')[:12]
        total_eventos = Evento.objects.count()
        # conta inscrições que ainda têm evento (eventos deletados ficam com evento=NULL)
        total_inscricoes = Inscricao.objects.filter(evento__isnull=False).count()

    # define quem pode criar eventos: Organizadores e staff (exclui Professores)
    can_create = request.user.groups.filter(name='Organizador').exists() or (request.user.is_staff and not request.user.groups.filter(name='Professor').exists())

    # opções de responsável: organizador vê Professores para atribuir
    if request.user.groups.filter(name='Organizador').exists():
        responsaveis = User.objects.filter(groups__name='Professor').distinct().order_by('first_name')
    else:
        # staff pode escolher outros staff (exclui superuser puro salvo se organizador)
        responsaveis = User.objects.filter(is_staff=True).filter(Q(is_superuser=False) | Q(groups__name='Organizador')).distinct().order_by('username')

    message = None
    message_type = None
    if request.method == 'POST':
        # bloqueia criar/editar/remover para Professores
        
        if request.user.groups.filter(name='Professor').exists() and request.POST.get('action') in ('create_event','edit_event','delete_event'):
            message = 'Ação não permitida: professores não podem criar/editar/remover eventos.'
            message_type = 'danger'
        else:
            # criar evento
            if request.POST.get('action') == 'create_event':
                nome = (request.POST.get('nome') or '').strip()
                descricao = (request.POST.get('descricao') or '').strip()
                data_inicio_raw = request.POST.get('data_inicio')
                data_fim_raw = request.POST.get('data_fim')
                local = (request.POST.get('local') or '').strip()
                try:
                    vagas = int(request.POST.get('vagas') or 0)
                except Exception:
                    vagas = 0
                banner = request.FILES.get('banner')

                # detecta AJAX para retornar erros em JSON
                is_ajax = (
                    request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
                    or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                    or 'application/json' in request.META.get('HTTP_ACCEPT', '')
                )

                # campos obrigatórios no servidor
                if not nome or not descricao or not data_inicio_raw or not data_fim_raw or not local or not banner:
                    message = 'Todos os campos são obrigatórios, incluindo o banner.'
                    message_type = 'danger'
                else:
                    # parseia datas e aplica timezone
                    from datetime import datetime
                    def parse_dt_local(s):
                        if not s:
                            return None
                        try:
                            # aceita ISO com timezone (ex.: 2025-12-12T20:00:00Z)
                            if s.endswith('Z') or ('+' in s[10:] or '-' in s[10:]):
                                # fromisoformat rejeita 'Z' — substitui por +00:00
                                s2 = s.replace('Z', '+00:00')
                                dt = datetime.fromisoformat(s2)
                                # se ficar naive, torna aware
                                if dj_timezone.is_naive(dt):
                                    dt = make_aware(dt, get_current_timezone())
                                return dt
                            # fallback: monta a partir de componentes (data local)
                            if 'T' in s:
                                date_part, time_part = s.split('T')
                            else:
                                date_part, time_part = s.split(' ')
                            y, m, d = [int(x) for x in date_part.split('-')]
                            hh, mm = [int(x) for x in time_part.split(':')[:2]]
                            dt = datetime(y, m, d, hh, mm, 0)
                            return make_aware(dt, get_current_timezone())
                        except Exception:
                            return None

                    data_inicio = parse_dt_local(data_inicio_raw)
                    data_fim = parse_dt_local(data_fim_raw)
                    logging.getLogger(__name__).info("admin_area create_event: parsed %s %s now=%s", data_inicio, data_fim, dj_timezone.now())
                    now = dj_timezone.now()
                    if not data_inicio or not data_fim:
                        message = 'Datas inválidas: verifique início e fim.'
                        message_type = 'danger'
                    elif data_inicio < now:
                        message = 'Não é possível criar um evento com data de início no passado.'
                        message_type = 'danger'
                    elif data_fim <= data_inicio:
                        message = 'Datas inválidas: verifique início e fim (fim deve ser posterior ao início).'
                        message_type = 'danger'
                    # se AJAX e validação falhou, retorna JSON com mensagem
                    if is_ajax and message_type == 'danger':
                        return JsonResponse({'status': 'error', 'message': message})
                    carga_minutes = int((data_fim - data_inicio).total_seconds() // 60)
                    # seleciona responsavel se informado (usa queryset já pronto)
                resp_id = request.POST.get('responsavel')
                responsavel = None
                if resp_id:
                    candidate = User.objects.filter(id=resp_id).first()
                    if candidate and responsaveis.filter(id=candidate.id).exists():
                        responsavel = candidate
                # se nenhum responsavel escolhido, usa usuário atual se elegível
                if responsavel is None and responsaveis.filter(id=request.user.id).exists():
                    responsavel = request.user
                evento = Evento(nome=nome, descricao=descricao, data_inicio=data_inicio, data_fim=data_fim, local=local, vagas=vagas, carga_horaria_minutos=carga_minutes, responsavel=responsavel)
                if isinstance(banner, UploadedFile):
                    evento.banner = banner
                try:
                            try:
                                evento.clean()
                            except Exception:
                                # ignora validação estrita do modelo para evitar HTML
                                pass
                            evento.save()
                            message = 'Evento criado com sucesso.'
                            message_type = 'success'
                            # registra auditoria detalhada da criação (inclui banner)
                            try:
                                try:
                                    banner_name = evento.banner.name if evento.banner and hasattr(evento.banner, 'name') else None
                                    banner_url = evento.banner.url if evento.banner and hasattr(evento.banner, 'url') else None
                                except Exception:
                                    banner_name = None
                                    banner_url = None
                                created_lines = [
                                    f"Evento id={evento.id}",
                                    f"nome: {evento.nome}",
                                    f"descricao: {evento.descricao}",
                                    f"data_inicio: {evento.data_inicio.strftime('%d/%m/%Y %H:%M') if evento.data_inicio else ''}",
                                    f"data_fim: {evento.data_fim.strftime('%d/%m/%Y %H:%M') if evento.data_fim else ''}",
                                    f"local: {evento.local}",
                                    f"vagas: {evento.vagas}",
                                    f"carga_horaria_minutos: {evento.carga_horaria_minutos}",
                                    f"responsavel_id: {evento.responsavel_id}",
                                    f"responsavel_name: {evento.responsavel.get_full_name() if evento.responsavel else ''}",
                                ]
                                if banner_name:
                                    created_lines.append(f"banner_name: {banner_name}")
                                if banner_url:
                                    created_lines.append(f"banner_url: {banner_url}")
                                details_txt = "\n".join(created_lines)
                                log_audit(request.user, 'Criou evento', details_txt)
                            except Exception:
                                pass
                            # se AJAX, retorna JSON com dados do evento e contagens
                            is_ajax = (
                                request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
                                or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                                or 'application/json' in request.META.get('HTTP_ACCEPT', '')
                            )
                            if is_ajax:
                                # recomputa totais como no topo da view
                                if request.user.groups.filter(name='Professor').exists():
                                    total_eventos = Evento.objects.filter(responsavel=request.user).count()
                                    total_inscricoes = Inscricao.objects.filter(evento__responsavel=request.user).count()
                                else:
                                    total_eventos = Evento.objects.count()
                                    total_inscricoes = Inscricao.objects.filter(evento__isnull=False).count()
                                resp_name = evento.responsavel.get_full_name() if evento.responsavel else ''
                                return JsonResponse({
                                    'status': 'ok',
                                    'evento': {
                                        'id': evento.id,
                                        'nome': evento.nome,
                                        'descricao': evento.descricao,
                                        'data_inicio': evento.data_inicio.isoformat() if evento.data_inicio else None,
                                        'data_fim': evento.data_fim.isoformat() if evento.data_fim else None,
                                        'vagas': evento.vagas,
                                        'carga_horaria_minutos': evento.carga_horaria_minutos,
                                        'responsavel_id': evento.responsavel_id,
                                        'responsavel_name': resp_name,
                                    },
                                    'total_eventos': total_eventos,
                                    'total_inscricoes': total_inscricoes,
                                })
                except Exception as e:
                    # em exceção inesperada, retorna JSON de erro para AJAX
                    message = f'Falha ao criar evento: {e}'
                    message_type = 'danger'
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': message}, status=500)
                # valida vagas não-negativas
                if vagas < 0:
                    message = 'Número de vagas inválido.'
                    message_type = 'danger'

            # editar evento
            if request.POST.get('action') == 'edit_event':
                event_id = request.POST.get('event_id')
                if event_id:
                    evento_obj = Evento.objects.filter(id=event_id).first()
                if evento_obj:
                    # pega campos (banner opcional no edit)
                    nome = (request.POST.get('nome') or '').strip()
                    descricao = (request.POST.get('descricao') or '').strip()
                    data_inicio_raw = request.POST.get('data_inicio')
                    data_fim_raw = request.POST.get('data_fim')
                    local = (request.POST.get('local') or '').strip()
                    try:
                        vagas = int(request.POST.get('vagas') or 0)
                    except Exception:
                        vagas = evento_obj.vagas
                    banner = request.FILES.get('banner')

                    from datetime import datetime
                    def parse_dt_local(s):
                        if not s:
                            return None
                        try:
                            if s.endswith('Z') or ('+' in s[10:] or '-' in s[10:]):
                                s2 = s.replace('Z', '+00:00')
                                dt = datetime.fromisoformat(s2)
                                if dj_timezone.is_naive(dt):
                                    dt = make_aware(dt, get_current_timezone())
                                return dt
                            if 'T' in s:
                                date_part, time_part = s.split('T')
                            else:
                                date_part, time_part = s.split(' ')
                            y, m, d = [int(x) for x in date_part.split('-')]
                            hh, mm = [int(x) for x in time_part.split(':')[:2]]
                            dt = datetime(y, m, d, hh, mm, 0)
                            return make_aware(dt, get_current_timezone())
                        except Exception:
                            return None

                    data_inicio = parse_dt_local(data_inicio_raw) or evento_obj.data_inicio
                    data_fim = parse_dt_local(data_fim_raw) or evento_obj.data_fim
                    logging.getLogger(__name__).info("admin_area edit_event: parsed %s %s now=%s", data_inicio, data_fim, dj_timezone.now())

                    if not nome or not descricao or not data_inicio or not data_fim or not local:
                        message = 'Todos os campos são obrigatórios (banner pode ficar inalterado no edit).'
                        message_type = 'danger'
                    else:
                        if data_fim <= data_inicio:
                            message = 'Datas inválidas: fim deve ser posterior ao início.'
                            message_type = 'danger'
                        else:
                            carga_minutes = int((data_fim - data_inicio).total_seconds() // 60)
                            # guarda valores antigos para diff
                            old = {
                                'nome': evento_obj.nome,
                                'descricao': evento_obj.descricao,
                                    'data_inicio': evento_obj.data_inicio.strftime('%d/%m/%Y %H:%M') if evento_obj.data_inicio else None,
                                'data_fim': evento_obj.data_fim.strftime('%d/%m/%Y %H:%M') if evento_obj.data_fim else None,
                                'local': evento_obj.local,
                                'vagas': evento_obj.vagas,
                                'carga_horaria_minutos': evento_obj.carga_horaria_minutos,
                                'responsavel_id': evento_obj.responsavel_id,
                            }
                            evento_obj.nome = nome
                            evento_obj.descricao = descricao
                            evento_obj.data_inicio = data_inicio
                            evento_obj.data_fim = data_fim
                            evento_obj.local = local
                            evento_obj.vagas = vagas
                            evento_obj.carga_horaria_minutos = carga_minutes
                            # atualiza responsavel se informado; mesmas escolhas de create
                            resp_id = request.POST.get('responsavel')
                            if resp_id:
                                candidate = User.objects.filter(id=resp_id).first()
                                if candidate and responsaveis.filter(id=candidate.id).exists():
                                    evento_obj.responsavel = candidate
                            if isinstance(banner, UploadedFile):
                                evento_obj.banner = banner
                            try:
                                evento_obj.clean()
                                evento_obj.save()
                                message = 'Evento atualizado.'
                                message_type = 'success'
                                # registra auditoria da edição com diffs
                                try:
                                    new = {
                                        'nome': evento_obj.nome,
                                        'descricao': evento_obj.descricao,
                                        'data_inicio': evento_obj.data_inicio.strftime('%d/%m/%Y %H:%M') if evento_obj.data_inicio else None,
                                        'data_fim': evento_obj.data_fim.strftime('%d/%m/%Y %H:%M') if evento_obj.data_fim else None,
                                        'local': evento_obj.local,
                                        'vagas': evento_obj.vagas,
                                        'carga_horaria_minutos': evento_obj.carga_horaria_minutos,
                                        'responsavel_id': evento_obj.responsavel_id,
                                    }
                                    # inclui url/nome do banner antigo/novo
                                    try:
                                        old_banner_url = evento_obj.banner.url if hasattr(evento_obj, 'banner') and evento_obj.banner else None
                                    except Exception:
                                        old_banner_url = None
                                    try:
                                        new_banner_url = evento_obj.banner.url if hasattr(evento_obj, 'banner') and evento_obj.banner else None
                                    except Exception:
                                        new_banner_url = None
                                    # calcula diffs e monta detalhes
                                    diffs = []
                                    for k in old.keys():
                                        if str(old.get(k)) != str(new.get(k)):
                                            diffs.append(f"{k}: {old.get(k)} -> {new.get(k)}")
                                    # diferenças no banner
                                    if old_banner_url or new_banner_url:
                                        diffs.append(f"banner_old: {old_banner_url}")
                                        diffs.append(f"banner_new: {new_banner_url}")
                                    details = "\n".join(diffs) if diffs else f'Evento id={evento_obj.id} sem alterações detectadas.'
                                    log_audit(request.user, 'Editou evento', f'Evento id={evento_obj.id}\n{details}')
                                except Exception:
                                    pass
                                # se AJAX, retorna JSON com evento atualizado e contagens
                                is_ajax = (
                                    request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
                                    or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                                    or 'application/json' in request.META.get('HTTP_ACCEPT', '')
                                )
                                if is_ajax:
                                    if request.user.groups.filter(name='Professor').exists():
                                        total_eventos = Evento.objects.filter(responsavel=request.user).count()
                                        total_inscricoes = Inscricao.objects.filter(evento__responsavel=request.user).count()
                                    else:
                                        total_eventos = Evento.objects.count()
                                        total_inscricoes = Inscricao.objects.filter(evento__isnull=False).count()
                                    resp_name = evento_obj.responsavel.get_full_name() if evento_obj.responsavel else ''
                                    return JsonResponse({
                                        'status': 'ok',
                                        'evento': {
                                            'id': evento_obj.id,
                                            'nome': evento_obj.nome,
                                            'descricao': evento_obj.descricao,
                                            'data_inicio': evento_obj.data_inicio.isoformat() if evento_obj.data_inicio else None,
                                            'data_fim': evento_obj.data_fim.isoformat() if evento_obj.data_fim else None,
                                            'vagas': evento_obj.vagas,
                                            'carga_horaria_minutos': evento_obj.carga_horaria_minutos,
                                            'responsavel_id': evento_obj.responsavel_id,
                                            'responsavel_name': resp_name,
                                        },
                                        'total_eventos': total_eventos,
                                        'total_inscricoes': total_inscricoes,
                                    })
                            except Exception as e:
                                message = f'Falha ao atualizar evento: {e}'
                                message_type = 'danger'
                                try:
                                    if is_ajax:
                                        return JsonResponse({'status': 'error', 'message': message}, status=500)
                                except Exception:
                                    pass
                            # valida vagas não-negativas
                            if vagas < 0:
                                message = 'Número de vagas inválido.'
                                message_type = 'danger'

        # deletar evento (mesmo nível de create/edit)
        if request.POST.get('action') == 'delete_event':
            eid = request.POST.get('event_id')
            if eid:
                e = Evento.objects.filter(id=eid).first()
                if e:
                    # guarda detalhes antes de deletar
                    _ev_id = e.id
                    _ev_nome = getattr(e, 'nome', '')
                    e.delete()
                    message = 'Evento removido.'
                    message_type = 'success'
                    # registra auditoria da remoção do evento
                    try:
                        log_audit(request.user, 'Removeu evento', f'Evento id={_ev_id} nome="{_ev_nome}"')
                    except Exception:
                        pass
                    # se AJAX, retorna JSON com totais atualizados
                    is_ajax = (
                        request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
                        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                        or 'application/json' in request.META.get('HTTP_ACCEPT', '')
                    )
                    if is_ajax:
                        if request.user.groups.filter(name='Professor').exists():
                            total_eventos = Evento.objects.filter(responsavel=request.user).count()
                            total_inscricoes = Inscricao.objects.filter(evento__responsavel=request.user).count()
                        else:
                            total_eventos = Evento.objects.count()
                            total_inscricoes = Inscricao.objects.filter(evento__isnull=False).count()
                        return JsonResponse({'status': 'ok', 'event_id': eid, 'total_eventos': total_eventos, 'total_inscricoes': total_inscricoes})




    # atualiza contadores e lista após ações

    # refresh (already computed above)

    # mostra botão de auditoria para Organizadores e superusers
    show_audit_button = request.user.groups.filter(name='Organizador').exists() or request.user.is_superuser

    return render(request, 'core/admin_area.html', {
        'total_eventos': total_eventos,
        'total_inscricoes': total_inscricoes,
        'recent_events': recent_events,
        'responsaveis': responsaveis,
        'can_create': can_create,
        'show_audit_button': show_audit_button,
        'message': message,
    })

    # se chegamos aqui via POST AJAX, retorna resumo JSON (catch-all)
    if request.method == 'POST' and (
        request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.META.get('HTTP_ACCEPT', '')
    ):
        try:
            # recomputa totais para a resposta
            if request.user.groups.filter(name='Professor').exists():
                total_eventos = Evento.objects.filter(responsavel=request.user).count()
                total_inscricoes = Inscricao.objects.filter(evento__responsavel=request.user).count()
            else:
                total_eventos = Evento.objects.count()
                total_inscricoes = Inscricao.objects.filter(evento__isnull=False).count()
        except Exception:
            total_eventos = None
            total_inscricoes = None
        status_flag = 'ok' if message_type == 'success' else 'error'
        return JsonResponse({'status': status_flag, 'message': message, 'total_eventos': total_eventos, 'total_inscricoes': total_inscricoes})


@login_required
@user_passes_test(lambda u: u.groups.filter(name='Organizador').exists() or u.is_superuser)
def admin_auditoria(request):
    # Auditoria list with filtering and pagination for Organizadores and superusers
    qs = Auditoria.objects.select_related('usuario').order_by('-data_hora')

    # filters: action, usuario (id or username), date_from, date_to
    action_q = (request.GET.get('action') or '').strip()
    usuario_q = (request.GET.get('usuario') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()

    if action_q:
        qs = qs.filter(acao__icontains=action_q)
    if usuario_q:
        # allow datalist values like "1 - Full Name" or plain id/username
        import re
        m = re.match(r'^\s*(\d+)', usuario_q)
        if m:
            qs = qs.filter(usuario__id=int(m.group(1)))
        else:
            qs = qs.filter(usuario__username__icontains=usuario_q)
    from datetime import datetime, timedelta
    try:
        if date_from:
            dt = datetime.strptime(date_from, '%Y-%m-%d')
            qs = qs.filter(data_hora__gte=dt)
        if date_to:
            dt2 = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            qs = qs.filter(data_hora__lt=dt2)
    except Exception:
        # ignore parse errors and continue unfiltered by date
        pass

    # optional: exclude access/view logs (to avoid self-noise)
    # optional: exclude access/view logs (to avoid self-noise)
    # default behaviour: when the page is first visited (no GET params) hide access logs.
    # If the user submitted the filters (request.GET present) and didn't include the checkbox,
    # treat that as the user explicitly unchecking it. If the checkbox key is present, use its value.
    if 'exclude_access' in request.GET:
        exclude_access_flag = request.GET.get('exclude_access') in ('1', 'true', 'on')
    else:
        exclude_access_flag = True if not request.GET else False
    if exclude_access_flag:
        qs = qs.exclude(acao__icontains='Acesso Auditoria')
        qs = qs.exclude(acao__icontains='Visualizou Auditoria')

    # pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page_num = request.GET.get('page', 1)
    paginator = Paginator(qs, 50)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    auditorias = page_obj.object_list

    # record audit access of the auditoria (unless excluded explicitly)
    try:
        if not exclude_access_flag:
            log_audit(request.user, 'Acesso Auditoria', f'Visualizou auditoria (filtros: action={action_q} usuario={usuario_q} date_from={date_from} date_to={date_to})')
    except Exception:
        pass

    # support download as plain text of currently filtered results
    if request.GET.get('download') == 'txt':
        lines = []
        for a in qs.order_by('-data_hora')[:1000]:
            user_repr = f"{a.usuario.get_full_name() or a.usuario.username} (id:{a.usuario.id})" if a.usuario else '-'
            try:
                ts = a.data_hora.strftime('%d/%m/%Y %H:%M:%S')
            except Exception:
                ts = str(a.data_hora)
            lines.append(f"{ts}\t{user_repr}\t{a.acao}\t{a.detalhes}")
        content = '\n'.join(lines)
        from django.http import HttpResponse
        resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="auditoria.txt"'
        return resp

    # build base query string without page for pagination links
    from urllib.parse import urlencode
    params = request.GET.copy()
    if 'page' in params:
        params.pop('page')
    base_qs = params.urlencode()

    action_choices = [
        'Consulta API','Inscrição criada','API Login','Visualizou/Baixou certificado','Logout','Criou evento','Editou evento','Removeu evento','Acesso Auditoria','Cancelou inscrição','Confirmou presença','Gerou certificado','Revogou presença','Confirmou presença (por código)','Cancelou inscrição (usuário)','Login','Criação de Usuário','Acesso Inscritos','Gerou código de confirmação','Alterou senha','Reenviou verificação'
    ]
    # provide user list for the usuario filter datalist
    users = User.objects.order_by('first_name', 'username').all()

    return render(request, 'core/auditoria.html', {
        'auditorias': auditorias,
        'page_obj': page_obj,
        'base_qs': base_qs,
        'filters': {'action': action_q, 'usuario': usuario_q, 'date_from': date_from, 'date_to': date_to, 'exclude_access': exclude_access_flag},
        'action_choices': action_choices,
        'users': users,
        'media_url': getattr(settings, 'MEDIA_URL', '/media/')
    })


@user_passes_test(lambda u: u.is_staff or u.is_superuser or u.groups.filter(name__in=['Professor','Organizador']).exists())
@csrf_protect
def admin_clear_auditoria(request):
    if request.method != 'POST':
        return HttpResponseForbidden('Método inválido')
    # create a TXT backup of current auditoria, save it to media/auditoria_backups, create a backup log entry (undeletable), then delete other entries
    try:
        qs_all = Auditoria.objects.order_by('data_hora').all()
        lines = []
        for a in qs_all:
            user_repr = f"{a.usuario.get_full_name() or a.usuario.username} (id:{a.usuario.id})" if a.usuario else '-'
            try:
                ts = a.data_hora.strftime('%d/%m/%Y %H:%M:%S')
            except Exception:
                ts = str(a.data_hora)
            lines.append(f"{ts}\t{user_repr}\t{a.acao}\t{a.detalhes}")
        content = '\n'.join(lines)
        # ensure folder exists
        backup_dir = os.path.join(settings.MEDIA_ROOT or 'media', 'auditoria_backups')
        os.makedirs(backup_dir, exist_ok=True)
        import datetime
        fname = f"auditoria_backup_{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.txt"
        fpath = os.path.join(backup_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as fh:
            fh.write(content)
        # store only filename in backup log (we'll provide a download view)
        try:
            backup_log = Auditoria.objects.create(usuario=request.user if request.user.is_authenticated else None, acao='Limpou auditoria', detalhes=fname)
        except Exception:
            backup_log = None
        # delete all entries except any 'Limpou auditoria' logs (preserve backups)
        try:
            if backup_log:
                Auditoria.objects.exclude(id=backup_log.id).exclude(acao='Limpou auditoria').delete()
            else:
                Auditoria.objects.exclude(acao='Limpou auditoria').delete()
        except Exception:
            pass
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Falha ao limpar auditoria: {e}'}, status=500)
    # respond with JSON for AJAX or redirect back
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})
    return redirect('admin_auditoria')


@user_passes_test(lambda u: u.is_staff or u.is_superuser or u.groups.filter(name__in=['Professor','Organizador']).exists())
def download_auditoria_backup(request, filename):
    # validate filename to avoid directory traversal
    import re
    if not re.match(r'^auditoria_backup_\d{8}T\d{6}Z\.txt$', filename):
        raise Http404()
    backup_dir = os.path.join(settings.MEDIA_ROOT or 'media', 'auditoria_backups')
    fpath = os.path.join(backup_dir, filename)
    if not os.path.exists(fpath):
        raise Http404()
    # serve as attachment
    return FileResponse(open(fpath, 'rb'), as_attachment=True, filename=filename)


def admin_event_inscritos(request, event_id):
    # show inscritos for an event; restrict access: staff/superuser and organizadores can access any;
    # professors can access only events where they are responsavel
    evento = Evento.objects.filter(id=event_id).first()
    if not evento:
        return HttpResponseForbidden('Evento não encontrado')
    # permission checks
    if request.user.is_superuser or request.user.is_staff:
        allowed = True
    elif request.user.groups.filter(name='Organizador').exists():
        allowed = True
    elif request.user.groups.filter(name='Professor').exists() and evento.responsavel == request.user:
        allowed = True
    else:
        allowed = False
    if not allowed:
        return HttpResponseForbidden('Acesso negado')
    inscritos = Inscricao.objects.filter(evento=evento).select_related('participante')
    # determine if current user can generate a confirmation code for this event
    can_generate_code = False
    if request.user.is_staff or request.user.is_superuser:
        can_generate_code = True
    if request.user.groups.filter(name='Organizador').exists():
        can_generate_code = True
    if request.user.groups.filter(name='Professor').exists() and evento.responsavel == request.user:
        can_generate_code = True

    # note: rendering the inscritos list is an audit-worthy access
    try:
        log_audit(request.user, 'Acesso Inscritos', f'Visualizou inscritos do evento id={evento.id} evento_name="{evento.nome if evento else ''}"')
    except Exception:
        pass
    # indicate if current user is Professor or Organizador (used by template for popup behavior)
    is_prof_or_org = request.user.groups.filter(name__in=['Professor','Organizador']).exists()
    return render(request, 'core/admin_inscritos.html', {'evento': evento, 'inscritos': inscritos, 'can_generate_code': can_generate_code, 'is_prof_or_org': is_prof_or_org})


@user_passes_test(lambda u: u.is_staff or u.is_superuser or u.groups.filter(name__in=['Professor','Organizador']).exists())
@csrf_protect
def cancelar_inscricao(request):
    if request.method != 'POST':
        return HttpResponseForbidden('Método inválido')
    iid = request.POST.get('inscricao_id')
    inscr = Inscricao.objects.filter(id=iid).select_related('evento').first()
    if not inscr:
        return HttpResponseForbidden('Inscrição não encontrada')
    evento = inscr.evento
    # permission: Professors can only cancel for events they created
    if request.user.groups.filter(name='Professor').exists():
        if not evento or evento.responsavel != request.user:
            return HttpResponseForbidden('Acesso negado')
    # capture details before deletion
    participante = inscr.participante
    evento = inscr.evento
    inscr_id = inscr.id
    # perform cancel
    inscr.delete()
    # log who canceled and context (Professor/Organizador/Staff)
    try:
        actor = request.user
        role = 'Staff' if (actor.is_staff or actor.is_superuser) else ('Organizador' if actor.groups.filter(name='Organizador').exists() else ('Professor' if actor.groups.filter(name='Professor').exists() else 'Unknown'))
        participante_name = None
        try:
            participante_name = (participante.get_full_name() or participante.username) if participante else None
        except Exception:
            participante_name = None
        details = f'Inscrição id={inscr_id} evento_id={evento.id if evento else None} participante_id={participante.id if participante else None} participante_name="{participante_name}"'
        log_audit(actor, f'Cancelou inscrição ({role})', details)
    except Exception:
        pass
    return JsonResponse({'status': 'ok'})


@user_passes_test(lambda u: u.is_staff or u.is_superuser or u.groups.filter(name__in=['Professor','Organizador']).exists())
@csrf_protect
def confirmar_presenca(request):
    if request.method != 'POST':
        return HttpResponseForbidden('Método inválido')
    iid = request.POST.get('inscricao_id')
    set_val = request.POST.get('set')  # optional '0' or '1'
    inscr = Inscricao.objects.filter(id=iid).select_related('evento').first()
    if not inscr:
        return JsonResponse({'status': 'error', 'message': 'Inscrição não encontrada'}, status=404)
    evento = inscr.evento
    # permission: Professors can only confirm for events they created
    if request.user.groups.filter(name='Professor').exists():
        if not evento or evento.responsavel != request.user:
            return HttpResponseForbidden('Acesso negado')

    # determine desired state: toggle if not provided
    if set_val is None:
        desired = not inscr.presenca_confirmada
    else:
        desired = bool(int(set_val))

    if desired:
        # confirm presence: set flag and generate certificate snapshot
        inscr.presenca_confirmada = True
        # snapshot certificate if not already generated
        if not inscr.certificado_gerado:
            evento = inscr.evento
            if evento:
                inscr.certificado_evento_nome = evento.nome
                inscr.certificado_data_inicio = evento.data_inicio
                inscr.certificado_local = evento.local
                inscr.certificado_carga_horaria_minutos = evento.carga_horaria_minutos
                inscr.certificado_emitido_em = timezone.now()
                inscr.certificado_gerado = True
        inscr.save()
        # log confirmation by admin (Professor/Organizador/Staff)
        try:
            actor = request.user
            role = 'Staff' if (actor.is_staff or actor.is_superuser) else ('Organizador' if actor.groups.filter(name='Organizador').exists() else ('Professor' if actor.groups.filter(name='Professor').exists() else 'Unknown'))
            participante_name = None
            try:
                participante_name = (inscr.participante.get_full_name() or inscr.participante.username) if inscr.participante else None
            except Exception:
                participante_name = None
            try:
                ev_name = evento.nome if evento else ''
            except Exception:
                ev_name = ''
            details = f'Inscrição id={inscr.id} evento_id={evento.id if evento else None} evento_name="{ev_name}" participante_id={inscr.participante_id} participante_name="{participante_name}"'
            log_audit(actor, f'Confirmou presença ({role})', details)
            # if certificate was generated now, log generation
            if inscr.certificado_gerado:
                log_audit(actor, 'Gerou certificado', details)
        except Exception:
            pass
        return JsonResponse({'status': 'ok', 'presenca': True})
    else:
        # un-confirm: clear presence and revoke generated certificate
        inscr.presenca_confirmada = False

        inscr.certificado_gerado = False
        inscr.certificado_emitido_em = None
        inscr.save()
        try:
            actor = request.user
            role = 'Staff' if (actor.is_staff or actor.is_superuser) else ('Organizador' if actor.groups.filter(name='Organizador').exists() else ('Professor' if actor.groups.filter(name='Professor').exists() else 'Unknown'))
            try:
                participante_name = (inscr.participante.get_full_name() or inscr.participante.username) if inscr.participante else None
            except Exception:
                participante_name = None
            try:
                ev_name = evento.nome if evento else ''
            except Exception:
                ev_name = ''
            log_audit(actor, f'Revogou presença ({role})', f'Inscrição id={inscr.id} evento_id={evento.id if evento else None} evento_name="{ev_name}" participante_id={inscr.participante_id} participante_name="{participante_name}"')
        except Exception:
            pass
        return JsonResponse({'status': 'ok', 'presenca': False})


@user_passes_test(lambda u: u.is_staff or u.is_superuser or u.groups.filter(name__in=['Professor','Organizador']).exists())
@csrf_protect
def generate_confirmation_code(request, event_id):
    # Only authorized users can generate a code
    evento = Evento.objects.filter(id=event_id).first()
    if not evento:
        return JsonResponse({'error': 'Evento não encontrado'}, status=404)

    # permission check: professor must be owner
    if request.user.groups.filter(name='Professor').exists() and evento.responsavel != request.user:
        return HttpResponseForbidden('Acesso negado')

    # only one code per event: return existing if present
    if evento.confirmation_code:
        return JsonResponse({'code': evento.confirmation_code})

    # generate a unique code per event (alphanumeric)
    import secrets, string
    alphabet = string.ascii_uppercase + string.digits

    def make_code(n=8):
        return ''.join(secrets.choice(alphabet) for _ in range(n))

    # ensure uniqueness across events
    for _ in range(10):
        code = make_code(8)
        if not Evento.objects.filter(confirmation_code=code).exists():
            evento.confirmation_code = code
            evento.save()
            # log generated code
            try:
                try:
                    ev_name = evento.nome if evento else ''
                except Exception:
                    ev_name = ''
                log_audit(request.user, 'Gerou código de confirmação', f'Evento id={evento.id} evento_name="{ev_name}" code={code}')
            except Exception:
                pass
            # if caller requested, send the code by email to all inscritos
            send_flag = False
            try:
                # accept form-encoded or JSON body
                if request.POST and request.POST.get('send'):
                    sv = request.POST.get('send')
                    send_flag = str(sv).lower() in ('1','true','yes')
                else:
                    import json as _json
                    try:
                        data = _json.loads(request.body.decode('utf-8') or '{}')
                        if data and data.get('send'):
                            send_flag = str(data.get('send')).lower() in ('1','true','yes')
                    except Exception:
                        send_flag = False
            except Exception:
                send_flag = False

            if send_flag:
                try:
                    from django.core.mail import EmailMultiAlternatives
                    from django.template.loader import render_to_string
                    from django.templatetags.static import static
                    from django.conf import settings
                    subject = f'Código de confirmação do evento {evento.nome}'
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None
                    inscricoes = Inscricao.objects.filter(evento=evento).select_related('participante')
                    for ins in inscricoes:
                        try:
                            participante = ins.participante
                            if not participante or not participante.email:
                                continue
                            text_content = render_to_string('core/email_event_code.txt', {'user': participante, 'evento': evento, 'code': code})
                            html_content = render_to_string('core/email_event_code.html', {'user': participante, 'evento': evento, 'code': code, 'logo_url': static('img/logo.png')})
                            msg = EmailMultiAlternatives(subject, text_content, from_email, [participante.email])
                            msg.attach_alternative(html_content, 'text/html')
                            msg.send(fail_silently=True)
                        except Exception:
                            continue
                except Exception:
                    pass

            return JsonResponse({'code': code})
    return JsonResponse({'error': 'Não foi possível gerar código'}, status=500)


@login_required
def confirmar_codigo_participante(request, inscricao_id):
    inscr = Inscricao.objects.filter(id=inscricao_id, participante=request.user).select_related('evento').first()
    if not inscr:
        return HttpResponseForbidden('Inscrição não encontrada')
    evento = inscr.evento
    if not evento:
        return HttpResponseForbidden('Evento não disponível')
    # only allow if event has finished
    if evento.data_fim > timezone.now():
        return HttpResponseForbidden('Evento ainda não finalizado')
    error = None
    success = False
    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        if not code:
            error = 'Código obrigatório.'
        elif not evento.confirmation_code:
            error = 'Nenhum código gerado para este evento.'
        elif code != evento.confirmation_code:
            error = 'Código inválido.'
        else:
            # mark presence and generate certificate
            inscr.presenca_confirmada = True
            if not inscr.certificado_gerado:
                inscr.certificado_evento_nome = evento.nome
                inscr.certificado_data_inicio = evento.data_inicio
                inscr.certificado_local = evento.local
                inscr.certificado_carga_horaria_minutos = evento.carga_horaria_minutos
                inscr.certificado_emitido_em = timezone.now()
                inscr.certificado_gerado = True
                inscr.save()
                # log confirmation via code (participant)
                try:
                    participante_name = None
                    try:
                        participante_name = (inscr.participante.get_full_name() or inscr.participante.username) if inscr.participante else None
                    except Exception:
                        participante_name = None
                    try:
                        ev_name = evento.nome if evento else ''
                    except Exception:
                        ev_name = ''
                    details = f'Inscrição id={inscr.id} evento_id={evento.id if evento else None} evento_name="{ev_name}" participante_id={inscr.participante_id} participante_name="{participante_name}"'
                    log_audit(request.user, 'Confirmou presença (por código)', details)
                    if inscr.certificado_gerado:
                        log_audit(request.user, 'Gerou certificado', details)
                except Exception:
                    pass
                success = True
    return render(request, 'core/confirmar_codigo.html', {'inscricao': inscr, 'evento': evento, 'error': error, 'success': success})


@login_required
@csrf_protect
def cancelar_minha_inscricao(request):
    if request.method != 'POST':
        return HttpResponseForbidden('Método inválido')
    evento_id = request.POST.get('evento_id')
    if not evento_id:
        return HttpResponseForbidden('Evento inválido')
    inscr = Inscricao.objects.filter(evento_id=evento_id, participante=request.user).first()
    if not inscr:
        return HttpResponseForbidden('Inscrição não encontrada')
    # log user-initiated cancellation
    try:
        participante_name = (request.user.get_full_name() or request.user.username)
        try:
            ev_obj = Evento.objects.filter(id=inscr.evento_id).first()
            ev_name = ev_obj.nome if ev_obj else ''
        except Exception:
            ev_name = ''
        log_audit(request.user, 'Cancelou inscrição (usuário)', f'Inscrição id={inscr.id} evento_id={inscr.evento_id} evento_name="{ev_name}" participante_id={request.user.id} participante_name="{participante_name}"')
    except Exception:
        pass
    inscr.delete()
    return redirect('home')


@csrf_protect
@never_cache
def login_view(request):
    # When showing the login page via GET, force logout so returning via browser
    # back button behaves like an explicit logout and avoids stale-auth errors.
    if request.method == 'GET' and request.user.is_authenticated:
        logout(request)
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # log successful login
            try:
                log_audit(user, 'Login', f'Login bem-sucedido')
            except Exception:
                pass
            return redirect('/home/')
        else:
            error = 'Usuário ou senha inválidos.'
    response = render(request, 'core/login.html', {'error': error})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


@csrf_exempt
@api_view(['POST'])
def api_login(request):
    # Simple token auth endpoint used by JS/admin scripts
    username = None
    password = None
    try:
        if isinstance(request.data, dict):
            username = request.data.get('username')
            password = request.data.get('password')
    except Exception:
        pass
    if not username:
        username = request.POST.get('username')
        password = request.POST.get('password')
    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({'error': 'Credenciais inválidas'}, status=401)
    token, _ = Token.objects.get_or_create(user=user)
    try:
        log_audit(user, 'API Login', 'Autenticou via API token')
    except Exception:
        pass
    return Response({'token': token.key})


def _make_code(n=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))


@csrf_protect
def register_view(request):
    error = None
    success = False
    if request.method == 'POST':
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        email = (request.POST.get('email') or '').strip().lower()
        telefone = (request.POST.get('telefone') or '').strip()
        data_nascimento_raw = (request.POST.get('data_nascimento') or '').strip()
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        # minimal validation
        if not first_name or not last_name or not email or not password or not password_confirm or not data_nascimento_raw or not telefone:
            error = 'Todos os campos obrigatórios devem ser preenchidos.'
        elif password != password_confirm:
            error = 'As senhas não coincidem.'
        elif get_user_model().objects.filter(email=email).exists():
            error = 'E-mail já cadastrado.'
        else:
            # enforce password strength server-side
            import re
            if len(password) < 8 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password) or not re.search(r'[^A-Za-z0-9]', password):
                error = 'Senha fraca: mínimo 8 caracteres, com letras, números e caracteres especiais.'
            else:
                # validate and normalize telefone before creating user
                try:
                    import re as _re
                    digits = _re.sub(r'\D', '', telefone or '')
                    # reject country code 55: user should provide only DDD and number
                    if digits.startswith('55'):
                        formatted_tel = None
                    else:
                        digits_local = digits
                        if len(digits_local) == 11:
                            formatted_tel = f"({digits_local[:2]}) {digits_local[2:7]}-{digits_local[7:]}"
                        elif len(digits_local) == 10:
                            formatted_tel = f"({digits_local[:2]}) {digits_local[2:6]}-{digits_local[6:]}"
                        else:
                            formatted_tel = None
                except Exception:
                    formatted_tel = None

                if not formatted_tel:
                    error = 'Telefone inválido: use o formato (XX) XXXXX-XXXX ou (XX) XXXX-XXXX.'
                else:
                    try:
                        from .models import UserProfile, EmailVerification
                        # create inactive user only after validations passed
                        user = User.objects.create_user(username=email, email=email, password=password, first_name=first_name, last_name=last_name, is_active=False)
                        profile = UserProfile.objects.create(user=user, telefone=formatted_tel)
                        # parse date: accept yyyy-mm-dd (from date input) or dd/mm/yy
                        if data_nascimento_raw:
                            try:
                                if '-' in data_nascimento_raw:
                                    yyyy, mm, dd = data_nascimento_raw.split('-')
                                    profile.data_nascimento = dj_timezone.datetime(int(yyyy), int(mm), int(dd)).date()
                                else:
                                    parts = data_nascimento_raw.split('/')
                                    if len(parts) == 3:
                                        d, m, y = parts
                                        if len(y) == 2:
                                            y = '20' + y
                                        profile.data_nascimento = dj_timezone.datetime(int(y), int(m), int(d)).date()
                            except Exception:
                                pass
                            profile.save()

                        # create email verification (rate-limited)
                        code = _make_code(6)
                        recent_day_count = EmailVerification.objects.filter(target_email=email, created_at__gte=dj_tz.now() - timedelta(days=1)).count()
                        last = EmailVerification.objects.filter(target_email=email).order_by('-created_at').first()
                        if recent_day_count >= 5:
                            error = 'Foram enviados muitos códigos para este e-mail. Tente novamente amanhã.'
                        elif last and (dj_tz.now() - last.created_at) < timedelta(minutes=2):
                            error = 'Aguarde alguns minutos antes de solicitar outro código.'
                        else:
                            # log creation of user with full details
                            try:
                                details_lines = [
                                    f"username: {user.username}",
                                    f"first_name: {user.first_name}",
                                    f"last_name: {user.last_name}",
                                    f"email: {user.email}",
                                    f"telefone: {profile.telefone if profile else ''}",
                                    f"data_nascimento: {profile.data_nascimento if profile and getattr(profile, 'data_nascimento', None) else ''}",
                                ]
                                details_txt = "\n".join(details_lines)
                                try:
                                    log_audit(user, 'Criação de Usuário', details_txt)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            ev = EmailVerification.objects.create(user=user, code=code, purpose='activate', target_email=email)
                            try:
                                log_audit(user, 'Enviou verificação', f'Verification id={ev.id} target={email}')
                            except Exception:
                                pass
                            subject = 'Código de verificação - SGEA'
                            text_content = render_to_string('core/email_verification.txt', {'user': user, 'code': code})
                            html_content = render_to_string('core/email_verification.html', {'user': user, 'code': code})
                            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None
                            try:
                                msg = EmailMultiAlternatives(subject, text_content, from_email, [email])
                                msg.attach_alternative(html_content, "text/html")
                                msg.send(fail_silently=False)
                            except Exception as e:
                                logging.getLogger(__name__).warning('Falha ao enviar e-mail de verificação: %s', e)
                            return redirect('verify', verification_id=ev.id)
                    except Exception as e:
                        error = f'Falha ao criar usuário: {e}'
    return render(request, 'core/register.html', {'error': error, 'success': success})


def admin_api_overview(request):
    """Admin/Organizador-only page listing internal API endpoints and notes.

    Explicitly check permissions so we can render a friendly rejection page
    for users who are not allowed (instead of raising 403).
    """
    allowed = False
    try:
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists()):
            allowed = True
    except Exception:
        allowed = False

    if not allowed:
        return render(request, 'core/admin_no_access.html', {})

    endpoints = [
        {'path': '/api/eventos/', 'desc': 'Listar/consultar eventos (token/session auth).'},
        {'path': '/api/inscricoes/', 'desc': 'Criar/listar inscrições do usuário autenticado.'},
        {'path': '/api-token-auth/', 'desc': 'Gerar token via usuário/senha para uso em API.'},
        {'path': '/api/internal/inscricoes/create-as/', 'desc': 'Criar inscrição para outro usuário (admin). JSON: {"evento":id, "user_id":id}.'},
        {'path': '/api/internal/eventos/<id>/inscricoes/', 'desc': 'Listar inscrições por evento (admin/organizador/professor). Query param optional: requesting_user_id=id'},
        {'path': '/api/internal/inscricoes/cancel-by/', 'desc': 'Cancelar inscrição por evento+usuario (JSON). POST {"evento_id":id, "target_user_id":id, "as_user_id":id}.'},
        {'path': '/api/internal/inscricoes/confirm-by/', 'desc': 'Confirmar presença por evento+usuario (JSON). POST {"evento_id":id, "target_user_id":id, "as_user_id":id}.'},
        {'path': '/api/internal/eventos/<id>/generate-code/', 'desc': 'Gerar código de confirmação para evento. POST JSON opcional: {"actor_user_id": id}.'},
    ]
    try:
        log_audit(request.user, 'Acesso API Overview', 'Visualizou lista de endpoints API')
    except Exception:
        pass
    return render(request, 'core/api_overview.html', {'endpoints': endpoints})


def admin_api_audits(request):
    """Return recent auditoria entries as JSON for admin/organizador users.

    Accept optional GET param `q` to filter action/detalhes, and `limit`.
    """
    # permission check: only staff/superuser or Organizadores
    try:
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists())):
            return JsonResponse({'error': 'Acesso negado'}, status=403)
    except Exception:
        return JsonResponse({'error': 'Acesso negado'}, status=403)

    q = (request.GET.get('q') or '').strip()
    try:
        limit = int(request.GET.get('limit') or 200)
    except Exception:
        limit = 200

    qs = Auditoria.objects.select_related('usuario').order_by('-data_hora')
    if q:
        qs = qs.filter(Q(acao__icontains=q) | Q(detalhes__icontains=q))
    qs = qs[:min(limit, 1000)]
    items = []
    for a in qs:
        usuario_repr = None
        try:
            usuario_repr = {'id': a.usuario.id, 'username': a.usuario.username}
        except Exception:
            usuario_repr = None
        items.append({
            'id': a.id,
            'usuario': usuario_repr,
            'acao': a.acao,
            'detalhes': a.detalhes,
            'data_hora': a.data_hora.isoformat() if a.data_hora else None,
        })
    return JsonResponse({'audits': items})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def api_cancel_inscricao(request, insc_id):
    # allow participant to cancel their own inscrição or staff/organizador
    inscr = Inscricao.objects.filter(id=insc_id).select_related('evento', 'participante').first()
    if not inscr:
        return Response({'error': 'Inscrição não encontrada'}, status=404)
    if request.user == inscr.participante or request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists():
        try:
            details = f'Inscrição id={inscr.id} evento_id={inscr.evento_id} participante_id={inscr.participante_id}'
            inscr.delete()
            try:
                log_audit(request.user, 'Cancelou inscrição (API)', details)
            except Exception:
                pass
            return Response({'status': 'ok'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
api_cancel_inscricao.throttle_scope = 'inscricao'


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def api_cancel_inscricao_as(request, insc_id=None):
    """Cancel an inscrição. Require JSON with 'evento_id' and 'target_user_id' and 'as_user_id'.
    If the caller supplies an `as_user_id` different from `request.user.id`, the caller must be staff/superuser or Organizador.
    The function will locate the inscrição by evento+participante and cancel it.
    """
    # parse JSON body
    try:
        data = request.data if isinstance(request.data, dict) else json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = {}
    evento_id = data.get('evento_id')
    target_user_id = data.get('target_user_id')
    as_user_id = data.get('as_user_id')

    if not evento_id or not target_user_id:
        return Response({'error': 'Forneça evento_id e target_user_id no corpo da requisição'}, status=400)

    # find inscrição
    insc = Inscricao.objects.filter(evento_id=evento_id, participante_id=target_user_id).first()
    if not insc:
        return Response({'error': 'Inscrição não encontrada para evento/usuário informados'}, status=404)

    # resolve acting user
    acting_user = None
    if as_user_id:
        if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists()):
            return Response({'error': 'Apenas administradores podem simular outro usuário'}, status=403)
        acting_user = User.objects.filter(id=as_user_id).first()
        if not acting_user:
            return Response({'error': 'Usuário simulado não encontrado'}, status=404)
        if str(acting_user.id) != str(target_user_id) and acting_user != insc.participante:
            # ensure the acting_user corresponds to the target participant
            return Response({'error': 'O usuário simulado não corresponde à inscrição'}, status=400)
    else:
        acting_user = request.user

    # permission check: acting_user must be participant or caller must be admin/organizador
    if acting_user == insc.participante or request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists():
        try:
            details = f'Inscrição id={insc.id} evento_id={insc.evento_id} participante_id={insc.participante_id} (cancelada por caller_id={request.user.id} acting_as={acting_user.id})'
            insc.delete()
            try:
                log_audit(request.user, 'Cancelou inscrição (API)', details)
            except Exception:
                pass
            return Response({'status': 'ok'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    return Response({'error': 'Acesso negado'}, status=403)
api_cancel_inscricao_as.throttle_scope = 'event-list'


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def api_confirm_inscricao_as(request, insc_id=None):
    """Confirm presence for inscrição. Require JSON with 'evento_id' and 'target_user_id' and 'as_user_id'."""
    try:
        data = request.data if isinstance(request.data, dict) else json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = {}
    evento_id = data.get('evento_id')
    target_user_id = data.get('target_user_id')
    as_user_id = data.get('as_user_id')

    if not evento_id or not target_user_id:
        return Response({'error': 'Forneça evento_id e target_user_id no corpo da requisição'}, status=400)

    insc = Inscricao.objects.filter(evento_id=evento_id, participante_id=target_user_id).select_related('evento').first()
    if not insc:
        return Response({'error': 'Inscrição não encontrada para evento/usuário informados'}, status=404)

    acting_user = None
    if as_user_id:
        if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists()):
            return Response({'error': 'Apenas administradores podem simular outro usuário'}, status=403)
        acting_user = User.objects.filter(id=as_user_id).first()
        if not acting_user:
            return Response({'error': 'Usuário simulado não encontrado'}, status=404)
        if str(acting_user.id) != str(target_user_id) and acting_user != insc.participante:
            return Response({'error': 'O usuário simulado não corresponde à inscrição'}, status=400)
    else:
        acting_user = request.user

    user = request.user
    if user.is_staff or user.is_superuser or user.groups.filter(name='Organizador').exists() or acting_user == insc.participante:
        insc.presenca_confirmada = True
        if not insc.certificado_gerado:
            evt = insc.evento
            if evt:
                insc.certificado_evento_nome = evt.nome
                insc.certificado_data_inicio = evt.data_inicio
                insc.certificado_local = evt.local
                insc.certificado_carga_horaria_minutos = evt.carga_horaria_minutos
                insc.certificado_emitido_em = timezone.now()
                insc.certificado_gerado = True
        insc.save()
        try:
            log_audit(request.user, 'Confirmou presença (API)', f'Inscrição id={insc.id} evento_id={insc.evento_id} participante_id={insc.participante_id} (confirmada por caller_id={request.user.id} acting_as={acting_user.id})')
        except Exception:
            pass
        return Response({'status': 'ok'})
    return Response({'error': 'Acesso negado'}, status=403)
api_confirm_inscricao_as.throttle_scope = 'event-list'


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def api_create_inscricao_as(request):
    """Create an inscrição for a specified user and event (admin/test helper).
    Expects JSON body: {"evento": <id>, "user_id": <id>}"""
    try:
        data = request.data if isinstance(request.data, dict) else json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = {}
    evento_id = data.get('evento')
    user_id = data.get('user_id')
    if not evento_id or not user_id:
        return Response({'error': 'Forneça evento e user_id'}, status=400)
    # only staff/superuser or organizador may simulate
    if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists()):
        return Response({'error': 'Apenas administradores podem criar inscrição como outro usuário'}, status=403)
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        return Response({'error': 'Usuário não encontrado'}, status=404)
    # disallow creating inscrição for organizers (maintain rule)
    if target_user.groups.filter(name='Organizador').exists():
        return Response({'error': 'Não é permitido inscrever um usuário do grupo Organizador'}, status=400)
    evento = Evento.objects.filter(id=evento_id).first()
    if not evento:
        return Response({'error': 'Evento não encontrado'}, status=404)
    now = timezone.now()
    if evento.data_fim and evento.data_fim <= now:
        return Response({'error': 'O evento já terminou'}, status=400)
    if evento.data_inicio and evento.data_inicio <= now < (evento.data_fim or (evento.data_inicio + timedelta(days=1))):
        return Response({'error': 'O evento já começou'}, status=400)
    # prevent duplicate
    if Inscricao.objects.filter(evento=evento, participante=target_user).exists():
        return Response({'error': 'Já existe inscrição para este usuário neste evento'}, status=400)
    insc = Inscricao(evento=evento, participante=target_user, criado_em=timezone.now())
    insc.save()
    try:
        log_audit(request.user, 'Criou inscrição (simulada)', f'Inscrição id={insc.id} evento_id={evento.id} participante_id={target_user.id}')
    except Exception:
        pass
    return Response({'status': 'ok', 'id': insc.id})
api_create_inscricao_as.throttle_scope = 'event-list'


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def api_list_event_inscricoes(request, event_id):
    """List inscriptions for a given event (admin/organizador/professor owner)."""
    evento = Evento.objects.filter(id=event_id).first()
    if not evento:
        return Response({'error': 'Evento não encontrado'}, status=404)
    # allow a 'requesting_user_id' query param to check permissions on behalf of that user
    req_user_id = request.GET.get('requesting_user_id')
    actor = request.user
    if req_user_id:
        # only admin/organizador may request on behalf of another user
        if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists()):
            return Response({'error': 'Apenas administradores podem consultar em nome de outro usuário'}, status=403)
        actor = User.objects.filter(id=req_user_id).first()
        if not actor:
            return Response({'error': 'Usuário requisitante não encontrado'}, status=404)

    # permission: staff/superuser or organizador or professor owner (for the actor)
    if not (actor.is_staff or actor.is_superuser or actor.groups.filter(name='Organizador').exists() or (actor.groups.filter(name='Professor').exists() and evento.responsavel == actor)):
        return Response({'error': 'Acesso negado'}, status=403)
    inscricoes = Inscricao.objects.filter(evento=evento).select_related('participante')
    out = []
    for i in inscricoes:
        out.append({'id': i.id, 'participante_id': i.participante_id, 'participante_username': getattr(i.participante, 'username', ''), 'presenca_confirmada': bool(i.presenca_confirmada)})
    return Response({'inscricoes': out})
api_list_event_inscricoes.throttle_scope = 'event-list'


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def api_confirm_inscricao(request, insc_id):
    # admin action: confirm presence for an inscrição
    inscr = Inscricao.objects.filter(id=insc_id).select_related('evento').first()
    if not inscr:
        return Response({'error': 'Inscrição não encontrada'}, status=404)
    # permission: staff/superuser or organizador or professor owner
    user = request.user
    if user.is_staff or user.is_superuser or user.groups.filter(name='Organizador').exists() or (user.groups.filter(name='Professor').exists() and inscr.evento and inscr.evento.responsavel == user):
        inscr.presenca_confirmada = True
        if not inscr.certificado_gerado:
            evt = inscr.evento
            if evt:
                inscr.certificado_evento_nome = evt.nome
                inscr.certificado_data_inicio = evt.data_inicio
                inscr.certificado_local = evt.local
                inscr.certificado_carga_horaria_minutos = evt.carga_horaria_minutos
                inscr.certificado_emitido_em = timezone.now()
                inscr.certificado_gerado = True
        inscr.save()
        try:
            log_audit(request.user, 'Confirmou presença (API)', f'Inscrição id={inscr.id} evento_id={inscr.evento_id} participante_id={inscr.participante_id}')
        except Exception:
            pass
        return Response({'status': 'ok'})
    return Response({'error': 'Acesso negado'}, status=403)
    api_confirm_inscricao.throttle_scope = 'inscricao'


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def api_generate_code(request, event_id):
    evento = Evento.objects.filter(id=event_id).first()
    if not evento:
        return Response({'error': 'Evento não encontrado'}, status=404)
    # allow specifying actor via JSON body 'actor_user_id'. If provided and different
    # from request.user, the caller must be staff/superuser or Organizador to simulate.
    try:
        data = request.data if isinstance(request.data, dict) else json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = {}
    actor_user_id = data.get('actor_user_id')
    actor = None
    if actor_user_id:
        # only allow simulation by admins/organizadores
        if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name='Organizador').exists()):
            return Response({'error': 'Apenas administradores podem gerar código em nome de outro usuário'}, status=403)
        actor = User.objects.filter(id=actor_user_id).first()
        if not actor:
            return Response({'error': 'Usuário especificado não encontrado'}, status=404)
    else:
        actor = request.user

    # forbid students explicitly as actors
    if actor.groups.filter(name='Aluno').exists():
        return Response({'error': 'Acesso negado para alunos'}, status=403)
    # permission: staff/superuser or organizador or professor owner
    if actor.groups.filter(name='Professor').exists() and evento.responsavel != actor and not (actor.is_staff or actor.is_superuser or actor.groups.filter(name='Organizador').exists()):
        return Response({'error': 'Acesso negado'}, status=403)
    if evento.confirmation_code:
        return Response({'code': evento.confirmation_code})
    import secrets, string
    alphabet = string.ascii_uppercase + string.digits
    def make_code(n=8):
        return ''.join(secrets.choice(alphabet) for _ in range(n))
    for _ in range(10):
        code = make_code(8)
        if not Evento.objects.filter(confirmation_code=code).exists():
            evento.confirmation_code = code
            evento.save()
            try:
                log_audit(request.user, 'Gerou código de confirmação (API)', f'Evento id={evento.id} code={code} actor_id={actor.id} caller_id={request.user.id}')
            except Exception:
                pass
            return Response({'code': code})
    return Response({'error': 'Não foi possível gerar código'}, status=500)

api_generate_code.throttle_scope = 'event-list'


@csrf_protect
def verify_view(request, verification_id):
    # verify by id and code
    from .models import EmailVerification
    ev = EmailVerification.objects.filter(id=verification_id).first()
    if not ev:
        return render(request, 'core/verify.html', {'error': 'Código inválido.'})
    error = None
    success = False
    # determine remaining cooldown for resend (seconds)
    remaining_seconds = 0
    try:
        last_ev = EmailVerification.objects.filter(target_email=ev.target_email).order_by('-created_at').first()
        if last_ev:
            delta = dj_tz.now() - last_ev.created_at
            if delta < timedelta(seconds=30):
                remaining_seconds = 30 - int(delta.total_seconds())
    except Exception:
        remaining_seconds = 0
    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        if not code:
            error = 'Código obrigatório.'
        elif ev.used or ev.code != code:
            error = 'Código inválido.'
        else:
            # activate user
            u = ev.user
            # ensure user is in 'Alunos' group
            try:
                alunos_group, _ = Group.objects.get_or_create(name='Alunos')
                if not u.groups.filter(name='Alunos').exists():
                    u.groups.add(alunos_group)
            except Exception:
                pass
            u.is_active = True
            u.save()
            try:
                log_audit(u, 'Confirmou verificação', f'Verification id={ev.id} target={ev.target_email}')
            except Exception:
                pass
            ev.used = True
            ev.save()
            # send welcome email with logo and user name
            try:
                subject_w = 'Bem-vindo ao SGEA'
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None
                text_content = render_to_string('core/email_welcome.txt', {'user': u})
                html_content = render_to_string('core/email_welcome.html', {'user': u, 'logo_url': static('img/logo.png')})
                msg2 = EmailMultiAlternatives(subject_w, text_content, from_email, [u.email])
                msg2.attach_alternative(html_content, 'text/html')
                msg2.send(fail_silently=True)
            except Exception:
                pass
            # auto-login and redirect to home
            login(request, u)
            return redirect('home')
    return render(request, 'core/verify.html', {'error': error, 'success': success, 'verification': ev, 'remaining_seconds': remaining_seconds})


@csrf_protect
def resend_verification(request, verification_id):
    # AJAX endpoint to resend a verification code (rate-limited)
    from .models import EmailVerification
    ev0 = EmailVerification.objects.filter(id=verification_id).first()
    if not ev0:
        return JsonResponse({'error': 'Código inválido.'}, status=404)
    email = ev0.target_email
    # enforce same limits as registration: max 5/day, min 2 minutes
    recent_day_count = EmailVerification.objects.filter(target_email=email, created_at__gte=dj_tz.now() - timedelta(days=1)).count()
    last = EmailVerification.objects.filter(target_email=email).order_by('-created_at').first()
    if recent_day_count >= 5:
        return JsonResponse({'error': 'Foram enviados muitos códigos para este e-mail. Tente novamente amanhã.'}, status=429)
    if last and (dj_tz.now() - last.created_at) < timedelta(seconds=30):
        # short-circuit: if less than 30s, ask client to wait
        return JsonResponse({'error': 'Aguarde alguns segundos antes de reenviar.'}, status=429)

    # create new verification record and email it
    code = _make_code(6)
    ev = EmailVerification.objects.create(user=ev0.user, code=code, purpose='activate', target_email=email)
    subject = 'Código de verificação - SGEA'
    text_content = render_to_string('core/email_verification.txt', {'user': ev.user, 'code': code})
    html_content = render_to_string('core/email_verification.html', {'user': ev.user, 'code': code})
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None
    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        logging.getLogger(__name__).warning('Falha ao reenviar e-mail de verificação: %s', e)

    # audit resend
    try:
        log_audit(request.user if request.user.is_authenticated else None, 'Reenviou verificação', f'Verification id={ev.id} target={email}')
    except Exception:
        pass
    return JsonResponse({'status': 'ok', 'new_id': ev.id})


@login_required
@csrf_protect
def profile_view(request):
    # edit personal data
    profile = getattr(request.user, 'profile', None)
    msg = None
    # on GET, attempt to normalize stored telefone values so the form's pattern won't reject valid numbers
    if request.method != 'POST' and profile and getattr(profile, 'telefone', None):
        try:
            import re
            orig = profile.telefone
            digits = re.sub(r'\D', '', orig or '')
            if digits.startswith('55'):
                digits_local = digits[2:]
            else:
                digits_local = digits
            if len(digits_local) == 11:
                formatted = f"({digits_local[:2]}) {digits_local[2:7]}-{digits_local[7:]}"
            elif len(digits_local) == 10:
                formatted = f"({digits_local[:2]}) {digits_local[2:6]}-{digits_local[6:]}"
            else:
                formatted = None
            if formatted and formatted != orig:
                profile.telefone = formatted
                try:
                    profile.save()
                except Exception:
                    pass
        except Exception:
            pass
    if request.method == 'POST':
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        telefone = (request.POST.get('telefone') or '').strip()
        data_nascimento_raw = (request.POST.get('data_nascimento') or '').strip()
        # capture old values for auditing
        old_user_first = request.user.first_name
        old_user_last = request.user.last_name
        old_profile_tel = profile.telefone if profile else ''
        old_profile_dob = getattr(profile, 'data_nascimento', None)
        old_photo_name = None
        try:
            if profile and getattr(profile, 'photo', None):
                old_photo_name = profile.photo.name
        except Exception:
            old_photo_name = None
        # validate telefone format (if provided) before saving to avoid invalid profile writes
        try:
            import re
            digits = re.sub(r'\D', '', telefone or '')
            if digits.startswith('55'):
                digits_local = digits[2:]
            else:
                digits_local = digits
            if telefone and len(digits_local) not in (10, 11):
                msg = 'Telefone inválido: use o formato (XX) XXXXX-XXXX ou (XX) XXXX-XXXX.'
                return render(request, 'core/profile.html', {'profile': profile, 'msg': msg})
        except Exception:
            # if normalization fails, treat as invalid input
            msg = 'Telefone inválido.'
            return render(request, 'core/profile.html', {'profile': profile, 'msg': msg})

        # update fields
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()
        if profile:
            # normalize and format telefone into (XX) XXXXX-XXXX or (XX) XXXX-XXXX
            try:
                import re
                digits = re.sub(r'\D', '', telefone or '')
                # strip leading country code 55 for formatting
                if digits.startswith('55'):
                    digits_local = digits[2:]
                else:
                    digits_local = digits
                formatted = telefone
                if len(digits_local) == 11:
                    formatted = f"({digits_local[:2]}) {digits_local[2:7]}-{digits_local[7:]}"
                elif len(digits_local) == 10:
                    formatted = f"({digits_local[:2]}) {digits_local[2:6]}-{digits_local[6:]}"
                else:
                    formatted = telefone
            except Exception:
                formatted = telefone
            profile.telefone = formatted
            if data_nascimento_raw:
                try:
                    if '-' in data_nascimento_raw:
                        # ISO date from input type=date
                        yyyy, mm, dd = data_nascimento_raw.split('-')
                        profile.data_nascimento = dj_timezone.datetime(int(yyyy), int(mm), int(dd)).date()
                    else:
                        parts = data_nascimento_raw.split('/')
                        if len(parts) == 3:
                            d, m, y = parts
                            if len(y) == 2:
                                y = '20' + y
                            profile.data_nascimento = dj_timezone.datetime(int(y), int(m), int(d)).date()
                except Exception:
                    pass
            if 'photo' in request.FILES:
                profile.photo = request.FILES['photo']
            profile.save()
        msg = 'Dados atualizados.'
        # build audit details comparing old and new
        try:
            changes = []
            if old_user_first != request.user.first_name:
                changes.append(f"first_name: {old_user_first} -> {request.user.first_name}")
            if old_user_last != request.user.last_name:
                changes.append(f"last_name: {old_user_last} -> {request.user.last_name}")
            if old_profile_tel != (profile.telefone if profile else ''):
                changes.append(f"telefone: {old_profile_tel} -> {profile.telefone}")
            dob_new = getattr(profile, 'data_nascimento', None)
            if (old_profile_dob and dob_new and str(old_profile_dob) != str(dob_new)) or (old_profile_dob and not dob_new) or (not old_profile_dob and dob_new):
                changes.append(f"data_nascimento: {old_profile_dob} -> {dob_new}")
            new_photo_name = None
            try:
                new_photo_name = profile.photo.name if profile and getattr(profile, 'photo', None) else None
            except Exception:
                new_photo_name = None
            if old_photo_name != new_photo_name:
                changes.append(f"photo: {old_photo_name or '-'} -> {new_photo_name or '-'}")
            if changes:
                details_txt = "\n".join(changes)
                try:
                    log_audit(request.user, 'Alterou dados', details_txt)
                except Exception:
                    pass
        except Exception:
            pass
    return render(request, 'core/profile.html', {'profile': profile, 'msg': msg})


@login_required
@csrf_protect
def change_password_view(request):
    error = None
    success = False
    # Two-step flow:
    # 1) Request code: POST with action=request_code and current_password -> sends EmailVerification (purpose=password_change)
    # 2) Confirm code: POST with action=confirm_code, verification_id, code, new_password -> apply change
    from .models import EmailVerification
    if request.method == 'POST':
        action = request.POST.get('action') or 'request_code'
        if action == 'request_code':
            current = request.POST.get('current_password')
            if not request.user.check_password(current):
                error = 'Senha atual incorreta.'
            else:
                # rate-limit: reuse same rules as verification
                email = request.user.email
                recent_day_count = EmailVerification.objects.filter(user=request.user, purpose='password_change', created_at__gte=dj_tz.now() - timedelta(days=1)).count()
                last = EmailVerification.objects.filter(user=request.user, purpose='password_change').order_by('-created_at').first()
                if recent_day_count >= 5:
                    error = 'Foram enviados muitos códigos. Tente novamente amanhã.'
                elif last and (dj_tz.now() - last.created_at) < timedelta(seconds=30):
                    error = 'Aguarde alguns segundos antes de reenviar.'
                else:
                    code = _make_code(6)
                    ev = EmailVerification.objects.create(user=request.user, code=code, purpose='password_change', target_email=email)
                    subject = 'Código para alteração de senha - SGEA'
                    text_content = render_to_string('core/email_password_change.txt', {'user': request.user, 'code': code})
                    html_content = render_to_string('core/email_password_change.html', {'user': request.user, 'code': code})
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None
                    try:
                        msg = EmailMultiAlternatives(subject, text_content, from_email, [email])
                        msg.attach_alternative(html_content, 'text/html')
                        msg.send(fail_silently=True)
                        # render template with verification info
                        return render(request, 'core/change_password.html', {'code_requested': True, 'verification': ev})
                    except Exception:
                        # failure to send is not fatal for user flow
                        return render(request, 'core/change_password.html', {'code_requested': True, 'verification': ev})
        if action == 'confirm_code':
            vid = request.POST.get('verification_id')
            code = (request.POST.get('code') or '').strip()
            newp = request.POST.get('new_password')
            newp_confirm = request.POST.get('new_password_confirm')
            ev = EmailVerification.objects.filter(id=vid, user=request.user, purpose='password_change').first()
            if not ev:
                error = 'Código inválido.'
            elif ev.used or ev.code != code:
                error = 'Código inválido.'
            elif not newp or newp != newp_confirm:
                error = 'As senhas não coincidem ou estão vazias.'
            else:
                # basic strength check
                import re
                if len(newp) < 8 or not re.search(r'[A-Za-z]', newp) or not re.search(r'\d', newp):
                    error = 'Senha fraca: mínimo 8 caracteres, inclua letras e números.'
                else:
                    request.user.set_password(newp)
                    request.user.save()
                    ev.used = True
                    ev.save()
                    success = True
                    try:
                        log_audit(request.user, 'Alterou senha', 'Usuário alterou sua senha via fluxo de recuperação')
                    except Exception:
                        pass
                    try:
                        # log logout and actually log the user out for safety
                        log_audit(request.user, 'Logout', 'Usuário efetuou logout após alterar senha')
                    except Exception:
                        pass
                    try:
                        from django.contrib.auth import logout as _dj_logout
                        _dj_logout(request)
                    except Exception:
                        pass
    # default render
    return render(request, 'core/change_password.html', {'error': error, 'success': success})
