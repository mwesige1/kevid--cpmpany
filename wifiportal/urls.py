from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from portal.views import captive_portal_check
from django.contrib.admin import AdminSite
AdminSite.has_permission = lambda self, request: request.user.is_active and request.user.is_superuser

urlpatterns = [

    # ── Captive Portal Detection ───────────────────────
    # Catches ALL OS captive portal checks
    path('generate_204',              captive_portal_check),  # Android
    path('gen_204',                   captive_portal_check),  # Android old
    path('connecttest.txt',           captive_portal_check),  # Windows
    path('redirect',                  captive_portal_check),  # Windows
    path('success.txt',               captive_portal_check),  # Firefox
    path('canonical.html',            captive_portal_check),  # Firefox
    path('hotspot-detect.html',       captive_portal_check),  # iOS/macOS
    path('library/test/success.html', captive_portal_check),  # iOS old
    path('ncsi.txt',                  captive_portal_check),  # Windows NCSI
    path('connectivity-check',        captive_portal_check),  # Ubuntu
    path('login',                     captive_portal_check),  # Mikrotik

    # ── Django Admin ───────────────────────────────────
    path('admin/', admin.site.urls),

    # ── Portal (Customer Facing) ───────────────────────
    path(
        '',
        include('portal.urls', namespace='portal')
    ),

    # ── Payments ───────────────────────────────────────
    path(
        'payments/',
        include('payments.urls', namespace='payments')
    ),

    # ── Dashboard (Admin Facing) ───────────────────────
    path(
        'dashboard/',
        include('dashboard.urls', namespace='dashboard')
    ),

    # ── Network ────────────────────────────────────────
    path(
        'network/',
        include('network.urls', namespace='network')
    ),

    path('favicon.ico', RedirectView.as_view(url='/static/images/favicon.ico')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)