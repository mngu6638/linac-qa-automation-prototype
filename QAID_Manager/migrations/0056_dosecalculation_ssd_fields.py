from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('QAID_Manager', '0055_dosecalculation_mu_linearity'),
    ]

    operations = [
        migrations.AddField(
            model_name='dosecalculation',
            name='absolute_setup_mode',
            field=models.CharField(default='SAD', max_length=10, verbose_name='Absolute Setup Mode'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='pdd_zref',
            field=models.FloatField(blank=True, null=True, verbose_name='PDD(zref) for SSD (%)'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='pdd_zref_source',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='PDD(zref) Source'),
        ),
    ]
