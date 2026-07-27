from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('QAID_Manager', '0054_film_analysis_band_width_default_8mm'),
    ]

    operations = [
        migrations.AddField(
            model_name='dosecalculation',
            name='mu_10',
            field=models.FloatField(blank=True, null=True, verbose_name='MU 10'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='mu_30',
            field=models.FloatField(blank=True, null=True, verbose_name='MU 30'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='mu_50',
            field=models.FloatField(blank=True, null=True, verbose_name='MU 50'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='mu_100',
            field=models.FloatField(blank=True, null=True, verbose_name='MU 100'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='mu_300',
            field=models.FloatField(blank=True, null=True, verbose_name='MU 300'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='mu_500',
            field=models.FloatField(blank=True, null=True, verbose_name='MU 500'),
        ),
        migrations.AddField(
            model_name='dosecalculation',
            name='mu_r2',
            field=models.FloatField(blank=True, null=True, verbose_name='MU Linearity R²'),
        ),
    ]
