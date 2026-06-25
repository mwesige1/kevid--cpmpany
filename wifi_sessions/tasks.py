from celery import shared_task
from django.utils import timezone
from portal.models import WiFiSession
from network.mikrotik import revoke_internet_access, grant_internet_access
import subprocess
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task
def check_expired_sessions():
    """
    Runs every 60 seconds via Celery Beat.

    Finds all sessions that have expired but are
    still marked as active in the database.
    For each expired session:
    1. Revokes internet access on the Mikrotik router
    2. Updates session status to 'expired' in database

    This is the most critical background task —
    it ensures customers cannot use internet
    after their paid time has run out.
    """

    # Find all sessions that should have expired by now
    # status='active' means we have not yet cut them off
    # expiry_time__lte=now means their time has passed
    expired_sessions = WiFiSession.objects.filter(
        status='active',
        expiry_time__lte=timezone.now()
    )

    # Count for logging purposes
    count = expired_sessions.count()
    logger.info(f"check_expired_sessions: found {count} expired sessions")

    for session in expired_sessions:
        try:
            # Step 1 — Revoke internet access on router
            # This cuts off the device's internet immediately
            revoke_internet_access(
                mac_address=session.device.mac_address,
                ip_address =session.ip_address,
                router     =session.router
            )

            # Step 2 — Update session status in database
            # This prevents the task from trying to expire it again
            session.status = 'expired'
            session.save()

            logger.info(
                f"Expired session for MAC: {session.device.mac_address}"
            )

        except Exception as e:
            # Log error but continue with other sessions
            # One failed session should not stop others from expiring
            logger.error(
                f"Failed to expire session {session.id}: {str(e)}"
            )

    return f"Processed {count} expired sessions"


@shared_task
def sync_active_sessions():
    """
    Runs every 60 seconds via Celery Beat.

    Handles devices that disconnected and reconnected
    with a new IP address from DHCP.

    When a device reconnects it may get a different IP.
    The old router rule points to the old IP so internet
    does not work. This task:
    1. Checks current IP for each active session device
    2. If IP changed — updates router rules and database
    3. Ensures router rules always match active sessions
    """

    # Get all sessions that are still active and not expired
    active_sessions = WiFiSession.objects.filter(
        status='active',
        expiry_time__gt=timezone.now()
    )

    for session in active_sessions:
        try:
            # Look up current IP for this MAC from ARP table
            current_ip = get_current_ip(session.device.mac_address)

            if current_ip is None:
                # Device not currently connected — skip
                continue

            if current_ip != session.ip_address:
                # IP has changed — device reconnected with new IP

                # Step 1 — Remove old router rule for previous IP
                revoke_internet_access(
                    mac_address=session.device.mac_address,
                    ip_address =session.ip_address,
                    router     =session.router
                )

                # Step 2 — Record old IP for logging
                old_ip = session.ip_address

                # Step 3 — Update session with new IP in database
                session.ip_address = current_ip
                session.save()

                # Step 4 — Add new router rule for new IP
                grant_internet_access(
                    mac_address=session.device.mac_address,
                    ip_address =current_ip,
                    router     =session.router
                )

                logger.info(
                    f"Updated IP for {session.device.mac_address}: "
                    f"{old_ip} → {current_ip}"
                )

        except Exception as e:
            logger.error(
                f"Failed to sync session {session.id}: {str(e)}"
            )

    return f"Synced {active_sessions.count()} active sessions"


@shared_task
def restore_router_rules():
    """
    Runs every 5 minutes via Celery Beat.
    Does two things:
    1. Re-applies router rules for all active sessions
       (safety net for router reboots)
    2. Removes stale bindings — bypassed bindings on
       Mikrotik that have no active session in database
       (cleans up after MAC randomization or missed expiry)
    """
    from network.models import MikroTikRouter
    from network.mikrotik import MikrotikAPI

    active_sessions = WiFiSession.objects.filter(
        status='active',
        expiry_time__gt=timezone.now()
    ).select_related('device', 'router')

    # Build set of MACs that should have internet access
    active_macs = set(
        s.device.mac_address for s in active_sessions
    )

    count = 0

    # ── Step 1 — Restore rules for all active sessions ─
    for session in active_sessions:
        try:
            grant_internet_access(
                mac_address=session.device.mac_address,
                ip_address =session.ip_address,
                router     =session.router
            )
            count += 1
        except Exception as e:
            logger.error(
                f"Failed to restore rule for session {session.id}: {str(e)}"
            )

    # ── Step 2 — Remove stale bindings ────────────────
    # Check all routers for bypassed bindings that have
    # no corresponding active session in the database
    routers = MikroTikRouter.objects.filter(status='online')

    for router in routers:
        try:
            api = MikrotikAPI(router=router)
            if not api.connect():
                continue
            if not api.login():
                api.disconnect()
                continue

            # Get all bypassed bindings from this router
            api.send_sentence([
                '/ip/hotspot/ip-binding/print',
                '?type=bypassed'
            ])
            response = api.read_sentence()
            api.disconnect()

            # Parse all bypassed bindings
            current_id  = None
            current_mac = None

            for word in response:
                if word.startswith('=.id='):
                    current_id  = word[5:]
                    current_mac = None
                elif word.startswith('=mac-address='):
                    current_mac = word[13:]
                elif word == '!re' and current_id and current_mac:
                    # Check if this MAC has an active session
                    if current_mac.upper() not in [m.upper() for m in active_macs]:
                        # No active session — remove stale binding
                        try:
                            api2 = MikrotikAPI(router=router)
                            api2.connect()
                            api2.login()
                            api2.send_sentence([
                                '/ip/hotspot/ip-binding/remove',
                                f'=.id={current_id}',
                            ])
                            api2.read_sentence()
                            api2.disconnect()
                            logger.warning(
                                f"🧹 Removed stale binding for {current_mac} on {router.identity}"
                            )
                        except Exception as e:
                            logger.error(f"Failed to remove stale binding: {e}")
                    current_id  = None
                    current_mac = None

        except Exception as e:
            logger.error(f"Stale binding cleanup error on {router.identity}: {e}")

    logger.info(f"restore_router_rules: restored {count} rules")
    return f"Restored {count} router rules"


@shared_task
def check_router_health():
    """
    Runs every 60 seconds via Celery Beat.
    Direct routers — checks API reachability.
    WireGuard routers — checks if polled recently.
    A WireGuard router is online if it polled within
    the last 30 seconds via the command queue endpoint.
    """
    from network.models import MikroTikRouter
    from network.mikrotik import is_router_reachable

    routers = MikroTikRouter.objects.all()
    cutoff  = timezone.now() - timedelta(seconds=30)

    for router in routers:
        try:
            if router.connection_type == 'wireguard':
                # ── WireGuard router ───────────────────────
                # VPS cannot reach router directly
                # Router polls every 2s — if last_seen is recent it's online
                if router.last_seen and router.last_seen >= cutoff:
                    router.status = 'online'
                else:
                    router.status = 'offline'
                router.save()

            else:
                # ── Direct router ──────────────────────────
                # Try to reach via API directly
                reachable     = is_router_reachable(router.connection_address)
                old_status    = router.status
                router.status = 'online' if reachable else 'offline'

                if reachable:
                    router.last_seen = timezone.now()

                router.save()

                if old_status != router.status:
                    logger.warning(
                        f"Router {router.identity} changed: "
                        f"{old_status} → {router.status}"
                    )

        except Exception as e:
            logger.error(
                f"Health check failed for router {router.identity}: {str(e)}"
            )

    return f"Health check completed for {routers.count()} routers"

def get_current_ip(mac_address):
    """
    Helper function that looks up the ARP table
    to find the current IP address for a given
    MAC address.

    The ARP table is maintained by the Linux kernel
    and maps IP addresses to MAC addresses for all
    devices currently on the network.

    Returns None if device is not currently connected.
    """

    try:
        # Run the Linux arp command to list all known devices
        # -n flag shows numeric addresses instead of hostnames
        result = subprocess.run(
            ['arp', '-n'],
            capture_output=True,
            text=True
        )

        # Parse each line looking for our MAC address
        for line in result.stdout.split('\n'):
            if mac_address.lower() in line.lower():
                parts = line.split()
                if len(parts) >= 1:
                    # First column is the IP address
                    return parts[0]

    except Exception as e:
        logger.error(f"ARP lookup error for {mac_address}: {str(e)}")

    return None