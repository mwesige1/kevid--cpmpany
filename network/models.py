from django.db import models


class MikroTikRouter(models.Model):
    """
    Represents a physical MikroTik router connected
    to our system. Each router serves a specific
    hotspot location and is managed remotely by
    our Django backend.

    The system monitors each router's health in
    real time — checking CPU, memory, and online
    status every few minutes via Celery tasks.

    Supports two connection methods:
    1. Direct API — connects via router's IP address
    2. WireGuard VPN — router creates a secure tunnel
       to our server (works even behind NAT)
    """

    STATUS_CHOICES = [
        ('online',  'Online'),   # Router is reachable and responding
        ('offline', 'Offline'),  # Router is not reachable
        ('pending', 'Pending'),  # Router added but not yet provisioned
    ]

    CONNECTION_CHOICES = [
        ('direct',    'Direct API'),     # Connect via router IP directly
        ('wireguard', 'WireGuard VPN'),  # Connect via VPN tunnel
    ]

    # ── Identity ───────────────────────────────────────
    identity         = models.CharField(max_length=100, unique=True)
    location         = models.CharField(
                           max_length=200,
                           blank=True,
                           help_text='e.g. Hotel Kampala, Entebbe Petrol Station'
                       )
    has_wireless     = models.BooleanField(default=True)

    # ── Connection Settings ────────────────────────────
    # How we connect to this router — Direct or WireGuard
    connection_type  = models.CharField(
                           max_length=15,
                           choices=CONNECTION_CHOICES,
                           default='direct'
                       )
    # Router's IP address on the local network
    ip_address       = models.GenericIPAddressField(
                           null=True,
                           blank=True
                       )
    # Port for Mikrotik API — default is 8728
    api_port         = models.IntegerField(default=8728)
    # Admin username for API access
    api_username     = models.CharField(max_length=100, default='admin')
    # Admin password for API access
    api_password     = models.CharField(max_length=100, blank=True)

    # ── WireGuard VPN ──────────────────────────────────
    # The VPN tunnel IP assigned to this router
    # Only used when connection_type is 'wireguard'
    wireguard_tunnel_ip = models.GenericIPAddressField(
                              null=True,
                              blank=True
                          )

    # ── Status & Health Monitoring ─────────────────────
    # Current online/offline/pending state
    status       = models.CharField(
                       max_length=10,
                       choices=STATUS_CHOICES,
                       default='pending'
                   )
    # Current CPU load percentage — updated by monitoring task
    cpu_usage    = models.FloatField(default=0)
    # Current memory usage percentage — updated by monitoring task
    memory_usage = models.FloatField(default=0)
    # Last time this router successfully responded to a health check
    last_seen    = models.DateTimeField(null=True, blank=True)

    # ── Hotspot Configuration ──────────────────────────
    # Whether hotspot service is enabled on this router
    hotspot_enabled = models.BooleanField(default=True)
    # IP range assigned to hotspot clients e.g. "192.168.1.0/24"
    hotspot_network = models.CharField(
                          max_length=20,
                          default='192.168.1.0/24'
                      )
    # Router's IP as the gateway for hotspot clients
    gateway_ip      = models.GenericIPAddressField(
                          default='192.168.1.1'
                      )
    # DNS servers given to hotspot clients — comma separated
    dns_servers     = models.CharField(
                          max_length=100,
                          default='8.8.8.8,8.8.4.4'
                      )

    # ── Timestamps ─────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['identity']

    def __str__(self):
        return f"{self.identity} — {self.status}"

    @property
    def is_online(self):
        """Returns True if router is currently online."""
        return self.status == 'online'

    @property
    def cpu_display(self):
        """Returns CPU usage as readable percentage string."""
        return f"{self.cpu_usage:.1f}%"

    @property
    def memory_display(self):
        """Returns memory usage as readable percentage string."""
        return f"{self.memory_usage:.1f}%"

    @property
    def connection_address(self):
        """
        Returns the correct IP address for connecting
        to this router based on the connection type.
        WireGuard uses the tunnel IP.
        Direct uses the router's actual IP.
        """
        if self.connection_type == 'wireguard':
            return self.wireguard_tunnel_ip
        return self.gateway_ip


class RouterCommand(models.Model):
    """
    Queue of commands for MikroTik routers.
    Router polls this table and executes pending commands.
    """

    ACTION_CHOICES = [
        ('grant',  'Grant Internet'),
        ('revoke', 'Revoke Internet'),
        ('block',  'Block Device'),
        ('unblock','Unblock Device'),
        ('reboot', 'Reboot Router'),
    ]

    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('executed', 'Executed'),
        ('failed',   'Failed'),
    ]

    # Which router should execute this command
    router      = models.ForeignKey(
                      MikroTikRouter,
                      on_delete=models.CASCADE,
                      related_name='commands'
                  )

    # What to do
    action      = models.CharField(max_length=10, choices=ACTION_CHOICES)

    # Target device
    mac_address = models.CharField(max_length=17)
    ip_address  = models.CharField(max_length=15, blank=True)

    # Status tracking
    status      = models.CharField(
                      max_length=10,
                      choices=STATUS_CHOICES,
                      default='pending'
                  )

    # Timestamps
    created_at  = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    # Error message if failed
    error       = models.TextField(blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.action} {self.mac_address} on {self.router.identity}"