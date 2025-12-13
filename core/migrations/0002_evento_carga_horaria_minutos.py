from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='evento',
            name='carga_horaria_minutos',
            field=models.PositiveIntegerField(default=240),
        ),
    ]
