from django.db import migrations, models


def deduplicate_film_analysis_parameters(apps, schema_editor):
    PhysicsParameters = apps.get_model('QAID_Manager', 'PhysicsParameters')
    params = list(
        PhysicsParameters.objects.filter(parameter_type='film_analysis').order_by('-updated_at', '-id')
    )
    if len(params) <= 1:
        return
    keeper = params[0]
    for duplicate in params[1:]:
        duplicate.delete()
    keeper.name = 'Film Analysis Parameters'
    keeper.is_active = True
    keeper.save(update_fields=['name', 'is_active'])


class Migration(migrations.Migration):

    dependencies = [
        ('QAID_Manager', '0051_film_analysis_physics_parameters'),
    ]

    operations = [
        migrations.RunPython(deduplicate_film_analysis_parameters, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='physicsparameters',
            constraint=models.UniqueConstraint(
                condition=models.Q(('parameter_type', 'film_analysis')),
                fields=('parameter_type',),
                name='unique_film_analysis_physics_parameter',
            ),
        ),
    ]
