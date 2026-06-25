from django.db import models


class Package(models.Model):

    DURATION_UNIT_CHOICES = [
        ('minutes', 'Minutes'),
        ('hours',  'Hours'),
        ('days',   'Days'),
        ('weeks',  'Weeks'),
        ('months', 'Months'),
    ]

    DATA_UNIT_CHOICES = [
        ('MB', 'MB'),
        ('GB', 'GB'),
    ]

    STATUS_CHOICES = [
        ('active',   'Active'),
        ('hidden',   'Hidden'),
        ('disabled', 'Disabled'),
    ]

    # ── Basic Configuration ────────────────────────────
    name          = models.CharField(max_length=100)
    duration      = models.IntegerField(default=1)
    duration_unit = models.CharField(
                        max_length=10,
                        choices=DURATION_UNIT_CHOICES,
                        default='days'
                    )
    description   = models.TextField(blank=True)

    # ── Speed & Performance ────────────────────────────
    upload_speed   = models.IntegerField(default=10)
    download_speed = models.IntegerField(default=10)
    data_limit     = models.DecimalField(
                        max_digits=10,
                        decimal_places=2,
                        null=True,
                        blank=True
                    )
    data_unit      = models.CharField(
                        max_length=5,
                        choices=DATA_UNIT_CHOICES,
                        default='GB'
                    )

    # ── Pricing & Devices ──────────────────────────────
    is_free_trial  = models.BooleanField(default=False)
    price          = models.DecimalField(
                        max_digits=10,
                        decimal_places=2,
                        default=0
                    )
    device_limit   = models.IntegerField(default=1)

    # ── Visibility ─────────────────────────────────────
    status        = models.CharField(
                        max_length=10,
                        choices=STATUS_CHOICES,
                        default='active'
                    )
    is_featured   = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)

    # ── Timestamps ─────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'price']

    def __str__(self):
        return f"{self.name} - UGX {self.price}"

    @property
    def duration_in_hours(self):
        if self.duration_unit == 'minutes':
            return self.duration / 60
        elif self.duration_unit == 'hours':
            return self.duration
        elif self.duration_unit == 'days':
            return self.duration * 24
        elif self.duration_unit == 'weeks':
            return self.duration * 24 * 7
        elif self.duration_unit == 'months':
            return self.duration * 24 * 30
        return self.duration * 24

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def speed_display(self):
        return f"↑{self.upload_speed} Mbps / ↓{self.download_speed} Mbps"

    @property
    def data_limit_display(self):
        if self.data_limit:
            return f"{self.data_limit} {self.data_unit}"
        return "Unlimited"


class Device(models.Model):
    mac_address  = models.CharField(max_length=17, unique=True)
    phone_number = models.CharField(max_length=15, blank=True)
    # Last router this device connected through
    last_router  = models.ForeignKey(
                       'network.MikroTikRouter',
                       on_delete=models.SET_NULL,
                       null=True,
                       blank=True,
                       related_name='devices'
                   )
    first_seen   = models.DateTimeField(auto_now_add=True)
    has_used_free_trial = models.BooleanField(default=False)
    last_seen    = models.DateTimeField(auto_now=True)
    total_spent  = models.DecimalField(
                       max_digits=10,
                       decimal_places=2,
                       default=0.00
                   )
    is_blocked   = models.BooleanField(default=False)

    class Meta:
        ordering = ['-last_seen']
        indexes  = [
            models.Index(fields=['mac_address']),
            models.Index(fields=['is_blocked']),
        ]

    def __str__(self):
        return f"{self.mac_address}"


class Customer(models.Model):

    STATUS_CHOICES = [
        ('active',    'Active'),
        ('pending',   'Pending'),
        ('expired',   'Expired'),
        ('suspended', 'Suspended'),
        ('paused',    'Paused'),
    ]

    # ── Personal Information ───────────────────────────
    first_name   = models.CharField(max_length=100, blank=True)
    last_name    = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, unique=True)
    email        = models.EmailField(blank=True)

    # ── Login Credentials ──────────────────────────────
    username     = models.CharField(max_length=100, unique=True)
    password     = models.CharField(max_length=255)

    # ── Linked Device ──────────────────────────────────
    device       = models.OneToOneField(
                       Device,
                       on_delete=models.SET_NULL,
                       null=True,
                       blank=True,
                       related_name='customer'
                   )

    # ── Package & Subscription ─────────────────────────
    package      = models.ForeignKey(
                       Package,
                       on_delete=models.SET_NULL,
                       null=True,
                       blank=True
                   )
    status       = models.CharField(
                       max_length=10,
                       choices=STATUS_CHOICES,
                       default='pending'
                   )
    expiry_date  = models.DateTimeField(null=True, blank=True)

    # ── Financial ──────────────────────────────────────
    total_spent  = models.DecimalField(
                       max_digits=10,
                       decimal_places=2,
                       default=0
                   )

    # ── Timestamps ─────────────────────────────────────
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"

    @property
    def full_name(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.phone_number

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expiry_date:
            return timezone.now() >= self.expiry_date
        return False


class WiFiSession(models.Model):
    """
    Represents an active internet connection granted
    to a device after successful payment or voucher
    redemption. This is the most critical model —
    Celery monitors every active session every minute
    to detect expiry and cut off internet access
    at the exact right moment.
    """

    STATUS_CHOICES = [
        ('active',    'Active'),    # Internet access currently granted
        ('expired',   'Expired'),   # Time ran out — access cut off
        ('cancelled', 'Cancelled'), # Admin manually disconnected
    ]

    # ── Relationships ──────────────────────────────────
    # The device that has internet access
    device      = models.ForeignKey(
                      Device,
                      on_delete=models.CASCADE
                  )
   # The package purchased for this session
    package     = models.ForeignKey(
                      Package,
                      on_delete=models.SET_NULL,
                      null=True,
                      blank=True
                  )
    # ── Router ─────────────────────────────────────────
    # The specific Mikrotik router this session is on
    # Null allowed for backwards compatibility
    router      = models.ForeignKey(
                      'network.MikroTikRouter',
                      on_delete=models.SET_NULL,
                      null=True,
                      blank=True,
                      related_name='sessions'
                  )
    

    # ── Network Details ────────────────────────────────
    # Current IP address of the device
    # Used in iptables/Mikrotik rules to grant access
    ip_address  = models.GenericIPAddressField()

    # ── Timing ─────────────────────────────────────────
    # Exact moment internet access was granted
    start_time  = models.DateTimeField(auto_now_add=True)
    # Exact moment access will be/was cut off
    expiry_time = models.DateTimeField()

    # ── Status ─────────────────────────────────────────
    # Current state of this session
    status      = models.CharField(
                      max_length=10,
                      choices=STATUS_CHOICES,
                      default='active'
                  )

    # ── Timestamps ─────────────────────────────────────
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['status']),
            models.Index(fields=['expiry_time']),
            models.Index(fields=['status', 'expiry_time']),
            models.Index(fields=['device', 'status']),
        ]

    def __str__(self):
        return f"{self.device.mac_address} — {self.package.name} — {self.status}"

    @property
    def time_remaining(self):
        """
        Calculates how much time is left in this session.
        Returns timedelta(0) if session has already expired.
        Used by the dashboard countdown timers.
        """
        from django.utils import timezone
        from datetime import timedelta
        remaining = self.expiry_time - timezone.now()
        return max(remaining, timedelta(0))

    @property
    def is_expired(self):
        """
        Returns True if expiry time has passed.
        Used by Celery task to find sessions to cut off.
        """
        from django.utils import timezone
        return timezone.now() >= self.expiry_time