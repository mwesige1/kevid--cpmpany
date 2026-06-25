from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [

    # ── Main Portal Pages ──────────────────────────────
    # Landing page — package selection and payment
    path(
        '',
        views.portal_landing,
        name='landing'
    ),

    # Connected page — shown after successful payment
    path(
        'connected/',
        views.connected,
        name='connected'
    ),

    # Blocked page — shown when device is blocked
    path(
        'blocked/',
        views.blocked,
        name='blocked'
    ),

    # Feedback submission from connected page
    path(
        'feedback/',
        views.submit_feedback,
        name='submit_feedback'
    ),

    path(
    'session-status/',
    views.session_status,
    name='session_status'
),
]