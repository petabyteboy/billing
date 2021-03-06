# Generated by Django 3.0.5 on 2020-04-30 13:42

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_auto_20200430_1331'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledgeritem',
            name='timestamp',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='ledgeritem',
            name='state',
            field=models.CharField(choices=[('P', 'Pending'), ('S', 'Processing'), ('F', 'Failed'), ('C', 'Completed')], default='P', max_length=1),
        ),
    ]
