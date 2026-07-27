from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


RUNTIME_SESSION_KEY = "_qaid_runtime_session_id"


@receiver(user_logged_in)
def bind_session_to_runtime(sender, request, user, **kwargs):
    runtime_id = getattr(settings, "QAID_RUNTIME_SESSION_ID", "").strip()
    if not runtime_id or request is None:
        return
    request.session[RUNTIME_SESSION_KEY] = runtime_id
