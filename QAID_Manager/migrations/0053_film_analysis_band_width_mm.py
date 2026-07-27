from django.db import migrations


def add_band_width_default(apps, schema_editor):
    PhysicsParameters = apps.get_model('QAID_Manager', 'PhysicsParameters')
    for param in PhysicsParameters.objects.filter(parameter_type='film_analysis'):
        values = dict(param.parameter_values) if isinstance(param.parameter_values, dict) else {}
        if 'field_size_band_width_mm' not in values:
            values['field_size_band_width_mm'] = 2.0
            param.parameter_values = values
            param.save(update_fields=['parameter_values'])


class Migration(migrations.Migration):

    dependencies = [
        ('QAID_Manager', '0052_deduplicate_film_analysis_parameters'),
    ]

    operations = [
        migrations.RunPython(add_band_width_default, migrations.RunPython.noop),
    ]
