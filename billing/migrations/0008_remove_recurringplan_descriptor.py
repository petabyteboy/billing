# Generated by Django 3.0.5 on 2020-05-14 11:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_auto_20200514_1032'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='recurringplan',
            name='descriptor',
        ),
    ]
