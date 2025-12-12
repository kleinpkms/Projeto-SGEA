from django.contrib import admin
from .models import Evento, Inscricao, Auditoria

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data_inicio', 'local', 'responsavel')

@admin.register(Inscricao)
class InscricaoAdmin(admin.ModelAdmin):
    list_display = ('evento', 'participante', 'data_inscricao')


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('data_hora', 'usuario', 'acao', 'detalhes')
    
    list_filter = ('data_hora', 'usuario') 
    
    search_fields = ('acao', 'detalhes', 'usuario__username')

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False