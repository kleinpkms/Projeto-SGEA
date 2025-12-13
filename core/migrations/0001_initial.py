import core.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Auditoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acao', models.CharField(max_length=255)),
                ('data_hora', models.DateTimeField(auto_now_add=True)),
                ('detalhes', models.TextField(blank=True, null=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Evento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200)),
                ('descricao', models.TextField(blank=True)),
                ('data_inicio', models.DateTimeField()),
                ('data_fim', models.DateTimeField()),
                ('local', models.CharField(max_length=200)),
                ('vagas', models.PositiveIntegerField()),
                ('banner', models.ImageField(blank=True, null=True, upload_to='banners/', validators=[core.models.validar_banner])),
                ('responsavel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='eventos_criados', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Inscricao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_inscricao', models.DateTimeField(auto_now_add=True)),
                ('presenca_confirmada', models.BooleanField(default=False)),
                ('certificado_gerado', models.BooleanField(default=False)),
                ('evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inscricoes', to='core.evento')),
                ('participante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inscricoes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('evento', 'participante')},
            },
        ),
    ]

