# Generated migration to add confirmation_code to Evento
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_inscricao_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='evento',
            name='confirmation_code',
            field=models.CharField(blank=True, max_length=32, null=True, unique=True),
        ),
    ]
