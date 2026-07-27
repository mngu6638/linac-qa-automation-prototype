from django.db import migrations


def set_band_width_default_8mm(apps, schema_editor):
    PhysicsParameters = apps.get_model('QAID_Manager', 'PhysicsParameters')
    for param in PhysicsParameters.objects.filter(parameter_type='film_analysis'):
        values = dict(param.parameter_values) if isinstance(param.parameter_values, dict) else {}
        current = values.get('field_size_band_width_mm')
        if current is None or float(current) == 2.0:
            values['field_size_band_width_mm'] = 8.0
            param.parameter_values = values
            param.save(update_fields=['parameter_values'])


class Migration(migrations.Migration):

    dependencies = [
        ('QAID_Manager', '0053_film_analysis_band_width_mm'),
    ]

    operations = [
        migrations.RunPython(set_band_width_default_8mm, migrations.RunPython.noop),
    ]
