from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventoViewSet, InscricaoViewSet
from .views import emitir_certificado

router = DefaultRouter()
router.register(r'eventos', EventoViewSet)
router.register(r'inscricoes', InscricaoViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('certificado/<int:inscricao_id>/', emitir_certificado, name='baixar_certificado'),
]