from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parser_api', '0009_add_scheduler_task'),
    ]

    operations = [
        migrations.AddField(
            model_name='info',
            name='batch_id',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='批次ID'),
        ),
        migrations.AddIndex(
            model_name='info',
            index=models.Index(fields=['platform', 'batch_id'], name='info_platform_batch_idx'),
        ),
    ]
