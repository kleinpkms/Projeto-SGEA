from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_datetime
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponseForbidden, JsonResponse
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
from django.contrib.sites.shortcuts import get_current_site
from django.templatetags.static import static
import secrets, string
from datetime import timedelta
from django.utils import timezone as dj_tz

User = get_user_model()


class EventoRateThrottle(UserRateThrottle):
    scope = 'event-list'


class InscricaoRateThrottle(UserRateThrottle):
    scope = 'inscricao'


class EventoViewSet(viewsets.ReadOnlyModelViewSet):
	# annotate events with inscritos count so serializer and clients can use it
	queryset = Evento.objects.all().annotate(inscricoes_count=Count('inscricoes'))
	serializer_class = EventoSerializer
	permission_classes = [permissions.IsAuthenticated]
	throttle_classes = [ScopedRateThrottle]
	throttle_scope = 'event-list'

	def list(self, request, *args, **kwargs):
		if request.user.is_authenticated:
			Auditoria.objects.create(usuario=request.user, acao='Consulta API', detalhes='Listou eventos via API')
		return super().list(request, *args, **kwargs)


class InscricaoViewSet(viewsets.ModelViewSet):
	queryset = Inscricao.objects.all()
	serializer_class = InscricaoSerializer
	permission_classes = [permissions.IsAuthenticated]
	throttle_classes = [ScopedRateThrottle]
	throttle_scope = 'inscricao'
	http_method_names = ['post', 'get']

	def get_queryset(self):
		return Inscricao.objects.filter(participante=self.request.user)

	def create(self, request, *args, **kwargs):
		# override to provide clearer error messages and to prevent inscriptions
		# for events that already started or finished. Also keep the friendly
		# organizer message behavior.
		# Extract evento id from incoming data if present
		evento_id = None
		if isinstance(request.data, dict):
			evento_id = request.data.get('evento')
		else:
			evento_id = request.POST.get('evento')
		# check timing constraints before attempting create
		if evento_id:
			evento = Evento.objects.filter(id=evento_id).first()
			if evento:
				now = timezone.now()
				# event finished
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
				# event in progress
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
			return super().create(request, *args, **kwargs)
		except Exception as e:
			# detect permission denial raised from serializer
			from rest_framework.exceptions import PermissionDenied as DRFPerm
			if isinstance(e, DRFPerm) or (hasattr(e, 'detail') and 'Organizador' in str(e)):
				# If the client expects HTML (browser / browsable API), return a small HTML page
				# that shows a JavaScript alert (pop-up) and navigates back. For API clients,
				# return JSON as before.
				accept = request.META.get('HTTP_ACCEPT', '')
				msg = 'Você faz parte do grupo Organizador e não pode se inscrever em eventos. Use uma conta de Aluno/Professor ou entre em contato com o administrador.'
				if 'text/html' in accept:
					# use json.dumps to safely encode the message as a JS string literal
					safe_msg = json.dumps(msg)
					html = '<html><head><meta charset="utf-8"><title>Acesso negado</title></head><body><script>try{alert(' + safe_msg + ');}catch(e){};try{window.history.back();}catch(e){window.location.href="/home/";}</script></body></html>'
					from django.http import HttpResponse
					return HttpResponse(html, status=403)
				return Response({'detail': msg}, status=status.HTTP_403_FORBIDDEN)
			# re-raise unexpected exceptions
			raise


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def api_login(request):
	username = request.data.get('username')
	password = request.data.get('password')
	user = authenticate(request, username=username, password=password)
	if user is None:
		return Response({'detail': 'Credenciais inválidas'}, status=status.HTTP_400_BAD_REQUEST)
	token, _ = Token.objects.get_or_create(user=user)
	return Response({'token': token.key})


@login_required
def emitir_certificado_view(request, inscricao_id):
	inscricao = get_object_or_404(Inscricao, id=inscricao_id)
	# Only allow rendering if certificado was generated
	if not inscricao.certificado_gerado:
		return HttpResponseForbidden('Certificado ainda não disponível.')
	return render(request, 'core/certificado.html', {'inscricao': inscricao, 'data_atual': timezone.now()})


@never_cache
def home(request):
	if not request.user.is_authenticated:
		return redirect('login')
	inscricoes = Inscricao.objects.filter(participante=request.user)
	eventos_qs = Evento.objects.all().annotate(inscricoes_count=Count('inscricoes')).order_by('data_inicio')
	inscricao_event_ids = list(inscricoes.values_list('evento_id', flat=True))

	# Server-side pagination for the feed (page param from GET)
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
		'now': timezone.now(),
	})
	# ensure browsers do not cache the authenticated home page
	response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
	response['Pragma'] = 'no-cache'
	return response


def sair(request):
	logout(request)
	return redirect('login')


@login_required
def admin_area(request):
	# if user is not authorized to view admin, show friendly message with back button
	if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=['Professor', 'Organizador']).exists()):
		return render(request, 'core/admin_no_access.html', {})
	# Simple admin area for staff/superuser to view quick stats
	# restrict list for Professors: only events they created
	if request.user.groups.filter(name='Professor').exists():
		recent_events = Evento.objects.filter(responsavel=request.user).order_by('-data_inicio')[:12]
		total_eventos = Evento.objects.filter(responsavel=request.user).count()
		# Professors see only inscrições for their own events
		total_inscricoes = Inscricao.objects.filter(evento__responsavel=request.user).count()
	else:
		recent_events = Evento.objects.all().order_by('-data_inicio')[:12]
		total_eventos = Evento.objects.count()
		# count only inscricoes that still reference an event (deleted events keep inscricoes with evento=NULL)
		total_inscricoes = Inscricao.objects.filter(evento__isnull=False).count()

	# determine who may create events: Organizadores and staff (but exclude users who are in 'Professor' group even if staff)
	can_create = request.user.groups.filter(name='Organizador').exists() or (request.user.is_staff and not request.user.groups.filter(name='Professor').exists())

	# responsavel choices: if organizer, list Professors so organizer can assign a Professor
	if request.user.groups.filter(name='Organizador').exists():
		responsaveis = User.objects.filter(groups__name='Professor').distinct().order_by('first_name')
	else:
		# staff can choose staff users (excluding raw superuser unless also Organizador)
		responsaveis = User.objects.filter(is_staff=True).filter(Q(is_superuser=False) | Q(groups__name='Organizador')).distinct().order_by('username')

	message = None
	message_type = None
	if request.method == 'POST':
		# protect create/edit/delete actions from Professors
		if request.user.groups.filter(name='Professor').exists() and request.POST.get('action') in ('create_event','edit_event','delete_event'):
			message = 'Ação não permitida: professores não podem criar/editar/remover eventos.'
			message_type = 'danger'
		else:
			# create event
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

				# required fields server-side
				if not nome or not descricao or not data_inicio_raw or not data_fim_raw or not local or not banner:
					message = 'Todos os campos são obrigatórios, incluindo o banner.'
					message_type = 'danger'
				else:
					# parse datetimes robustly and make them timezone-aware
					from datetime import datetime
					def parse_dt_local(s):
						if not s:
							return None
						try:
							# accept full ISO strings with timezone (e.g. 2025-12-12T20:00:00Z or +02:00)
							if s.endswith('Z') or ('+' in s[10:] or '-' in s[10:]):
								# Python's fromisoformat doesn't accept 'Z', replace with +00:00
								s2 = s.replace('Z', '+00:00')
								dt = datetime.fromisoformat(s2)
								# if returned naive (unlikely), make aware
								if dj_timezone.is_naive(dt):
									dt = make_aware(dt, get_current_timezone())
								return dt
							# fallback: build from components (local date/time string)
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

					if not data_inicio or not data_fim or data_fim <= data_inicio:
						message = 'Datas inválidas: verifique início e fim (fim deve ser posterior ao início).'
						message_type = 'danger'
					else:
						# compute carga in minutes
						carga_minutes = int((data_fim - data_inicio).total_seconds() // 60)
						# select responsavel if provided; use the precomputed `responsaveis` queryset
						resp_id = request.POST.get('responsavel')
						responsavel = None
						if resp_id:
							candidate = User.objects.filter(id=resp_id).first()
							if candidate and responsaveis.filter(id=candidate.id).exists():
								responsavel = candidate
						# if no responsavel explicitly chosen, set to current user only if they are in responsaveis
						if responsavel is None and responsaveis.filter(id=request.user.id).exists():
							responsavel = request.user
						evento = Evento(nome=nome, descricao=descricao, data_inicio=data_inicio, data_fim=data_fim, local=local, vagas=vagas, carga_horaria_minutos=carga_minutes, responsavel=responsavel)
						if isinstance(banner, UploadedFile):
							evento.banner = banner
						try:
							evento.clean()
							evento.save()
							message = 'Evento criado com sucesso.'
							message_type = 'success'
						except Exception as e:
							message = f'Falha ao criar evento: {e}'
							message_type = 'danger'
						# validate vagas non-negative
						if vagas < 0:
							message = 'Número de vagas inválido.'
							message_type = 'danger'

			# edit event
			if request.POST.get('action') == 'edit_event':
				event_id = request.POST.get('event_id')
				if event_id:
					evento_obj = Evento.objects.filter(id=event_id).first()
				if evento_obj:
					# gather fields (banner optional on edit)
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
							evento_obj.nome = nome
							evento_obj.descricao = descricao
							evento_obj.data_inicio = data_inicio
							evento_obj.data_fim = data_fim
							evento_obj.local = local
							evento_obj.vagas = vagas
							evento_obj.carga_horaria_minutos = carga_minutes
							# update responsavel if provided; use the same `responsaveis` choices as create
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
							except Exception as e:
								message = f'Falha ao atualizar evento: {e}'
								message_type = 'danger'
							# validate vagas non-negative
							if vagas < 0:
								message = 'Número de vagas inválido.'
								message_type = 'danger'

		# delete event (handled at same level as create/edit)
		if request.POST.get('action') == 'delete_event':
			eid = request.POST.get('event_id')
			if eid:
				e = Evento.objects.filter(id=eid).first()
				if e:
					e.delete()
					message = 'Evento removido.'
					message_type = 'success'




	# refresh counts and list after any action

	# refresh (already computed above)

	return render(request, 'core/admin_area.html', {
		'total_eventos': total_eventos,
		'total_inscricoes': total_inscricoes,
		'recent_events': recent_events,
		'responsaveis': responsaveis,
		'can_create': can_create,
		'message': message,
	})


@login_required
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

	return render(request, 'core/admin_inscritos.html', {'evento': evento, 'inscritos': inscritos, 'can_generate_code': can_generate_code})


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
	# perform cancel
	inscr.delete()
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
        return JsonResponse({'status': 'ok', 'presenca': True})
    else:
        # un-confirm: clear presence and revoke generated certificate
        inscr.presenca_confirmada = False
        inscr.certificado_gerado = False
        inscr.certificado_emitido_em = None
        inscr.save()
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
			return redirect('/home/')
		else:
			error = 'Usuário ou senha inválidos.'
	response = render(request, 'core/login.html', {'error': error})
	response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
	response['Pragma'] = 'no-cache'
	return response


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
		if not first_name or not last_name or not email or not password or not password_confirm:
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
				# create inactive user
				user = User.objects.create_user(username=email, email=email, password=password, first_name=first_name, last_name=last_name, is_active=False)
			# profile
			try:
				from .models import UserProfile, EmailVerification
				profile = UserProfile.objects.create(user=user, telefone=telefone)
				# parse date: accept yyyy-mm-dd (from date input) or dd/mm/yy
				if data_nascimento_raw:
					try:
						if '-' in data_nascimento_raw:
							# ISO date
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
				# create email verification
				code = _make_code(6)
				# rate-limit: no more than 5 codes per day, and at least 2 minutes between codes
				recent_day_count = EmailVerification.objects.filter(target_email=email, created_at__gte=dj_tz.now() - timedelta(days=1)).count()
				last = EmailVerification.objects.filter(target_email=email).order_by('-created_at').first()
				if recent_day_count >= 5:
					error = 'Foram enviados muitos códigos para este e-mail. Tente novamente amanhã.'
				elif last and (dj_tz.now() - last.created_at) < timedelta(minutes=2):
					error = 'Aguarde alguns minutos antes de solicitar outro código.'
				else:
					ev = EmailVerification.objects.create(user=user, code=code, purpose='activate', target_email=email)
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
	return JsonResponse({'status': 'ok', 'new_id': ev.id})


@login_required
@csrf_protect
def profile_view(request):
	# edit personal data
	profile = getattr(request.user, 'profile', None)
	msg = None
	if request.method == 'POST':
		first_name = (request.POST.get('first_name') or '').strip()
		last_name = (request.POST.get('last_name') or '').strip()
		telefone = (request.POST.get('telefone') or '').strip()
		data_nascimento_raw = (request.POST.get('data_nascimento') or '').strip()
		# update fields
		request.user.first_name = first_name
		request.user.last_name = last_name
		request.user.save()
		if profile:
			profile.telefone = telefone
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
	# default render
	return render(request, 'core/change_password.html', {'error': error, 'success': success})
