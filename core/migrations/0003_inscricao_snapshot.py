# Generated migration to add snapshot fields to Inscricao and make evento nullable
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_evento_carga_horaria_minutos'),
    ]

    operations = [
        migrations.AddField(
            model_name='inscricao',
            name='certificado_evento_nome',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='inscricao',
            name='certificado_data_inicio',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='inscricao',
            name='certificado_local',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='inscricao',
            name='certificado_carga_horaria_minutos',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='inscricao',
            name='certificado_emitido_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='inscricao',
            name='evento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inscricoes', to='core.evento'),
        ),
    ]
