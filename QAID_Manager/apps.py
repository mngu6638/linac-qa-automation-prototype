from django.apps import AppConfig


class QaidManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'QAID_Manager'

    def ready(self):
        from . import session_hooks  # noqa: F401
