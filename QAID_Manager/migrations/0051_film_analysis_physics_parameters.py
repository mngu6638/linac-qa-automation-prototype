from django.db import migrations


def seed_film_analysis_parameters(apps, schema_editor):
    PhysicsParameters = apps.get_model('QAID_Manager', 'PhysicsParameters')
    exists = PhysicsParameters.objects.filter(parameter_type='film_analysis').exists()
    if not exists:
        PhysicsParameters.objects.create(
            name='Film Analysis Parameters',
            parameter_type='film_analysis',
            energy='',
            beam_type='photon',
            parameter_values={'field_size_detection_threshold': 0.3},
            description='Configurable parameters for film analysis algorithms.',
            is_active=True,
        )


def unseed_film_analysis_parameters(apps, schema_editor):
    PhysicsParameters = apps.get_model('QAID_Manager', 'PhysicsParameters')
    PhysicsParameters.objects.filter(parameter_type='film_analysis').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('QAID_Manager', '0050_qarecord_draft_dose_calculation_state'),
    ]

    operations = [
        migrations.RunPython(seed_film_analysis_parameters, unseed_film_analysis_parameters),
    ]
