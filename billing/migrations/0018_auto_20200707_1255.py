# Generated by Django 3.0.5 on 2020-07-07 12:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0017_chargestate_last_error'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ledgeritem',
            name='account',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='billing.Account'),
        ),
    ]
