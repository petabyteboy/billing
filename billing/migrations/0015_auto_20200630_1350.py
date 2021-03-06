# Generated by Django 3.0.5 on 2020-06-30 13:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0014_auto_20200628_1921'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledgeritem',
            name='is_reversal',
            field=models.BooleanField(blank=True, default=False),
        ),
        migrations.AddField(
            model_name='subscription',
            name='amount_unpaid',
            field=models.DecimalField(decimal_places=2, default='0', max_digits=9),
        ),
    ]
