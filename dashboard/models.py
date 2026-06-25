from django.db import models
from portal.models import Package, Device, Customer, WiFiSession


class Expense(models.Model):
    """
    Tracks all business expenses for the WiFi operation.
    Used in financial analytics to calculate net profit
    by subtracting total expenses from total revenue.
    Examples: internet bills, equipment purchases,
    staff salaries, transport costs.
    """

    PAYMENT_METHOD_CHOICES = [
        ('cash',         'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('bank',         'Bank Transfer'),
        ('card',         'Card'),
        ('other',        'Other'),
    ]

    # ── Expense Details ────────────────────────────────
    # Name of the expense e.g. "Monthly Internet Bill"
    name           = models.CharField(max_length=200)
    # Category e.g. "Internet", "Salary", "Equipment"
    expense_type   = models.CharField(max_length=100)
    # Amount spent in UGX
    amount         = models.DecimalField(
                         max_digits=10,
                         decimal_places=2
                     )
    # The actual date of the expense — not when it was recorded
    date           = models.DateField()
    # How the expense was paid
    payment_method = models.CharField(
                         max_length=20,
                         choices=PAYMENT_METHOD_CHOICES,
                         default='cash'
                     )

    # ── Vendor Information ─────────────────────────────
    # Who was paid e.g. "MTN Uganda", "Airtel Uganda"
    vendor         = models.CharField(max_length=200, blank=True)

    # ── Receipt & Notes ────────────────────────────────
    # Photo of the receipt — stored in media/receipts/ folder
    receipt        = models.ImageField(
                         upload_to='receipts/',
                         null=True,
                         blank=True
                     )
    # Additional notes about this expense
    description    = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        # Most recent expenses shown first
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.name} — UGX {self.amount} ({self.date})"


class Lead(models.Model):
    """
    Tracks potential customers who have shown interest
    in the WiFi service but have not yet subscribed.
    Acts as a simple CRM (Customer Relationship Manager)
    to help staff follow up and convert leads into
    paying customers.
    Pipeline: New → Contacted → Free Trial → Converted/Lost
    """

    STATUS_CHOICES = [
        ('new',        'New'),         # Just captured, not yet contacted
        ('contacted',  'Contacted'),   # We have spoken to them
        ('free_trial', 'Free Trial'),  # Currently on a free trial
        ('converted',  'Converted'),   # Now a paying customer
        ('lost',       'Lost'),        # No longer interested
    ]

    SOURCE_CHOICES = [
        ('walk_in',      'Walk-in'),      # Came to our location
        ('referral',     'Referral'),     # Referred by existing customer
        ('social_media', 'Social Media'), # Found us online
        ('phone_call',   'Phone Call'),   # Called us directly
        ('other',        'Other'),        # Any other source
    ]

    # ── Contact Information ────────────────────────────
    # Lead's full name
    full_name        = models.CharField(max_length=200)
    # Primary phone number
    phone_number = models.CharField(max_length=15, blank=True, default='')    # Alternative phone number
    phone_number_alt = models.CharField(max_length=15, blank=True)
    # Email address
    email            = models.EmailField(blank=True)
    # Physical address — useful for home installation leads
    address          = models.TextField(blank=True)

    # ── Lead Details ───────────────────────────────────
    # Current stage in the pipeline
    status             = models.CharField(
                             max_length=15,
                             choices=STATUS_CHOICES,
                             default='new'
                         )
    # How we acquired this lead
    source             = models.CharField(
                             max_length=15,
                             choices=SOURCE_CHOICES,
                             default='other'
                         )
    # Which package the lead is interested in
    interested_package = models.ForeignKey(
                             Package,
                             on_delete=models.SET_NULL,
                             null=True,
                             blank=True
                         )
    # Which staff member is handling this lead
    assigned_to        = models.ForeignKey(
                             'auth.User',
                             on_delete=models.SET_NULL,
                             null=True,
                             blank=True
                         )

    # ── Notes & Follow-up ──────────────────────────────
    # Free text notes about conversations with the lead
    notes          = models.TextField(blank=True)
    # When we last spoke to this lead
    last_contacted = models.DateTimeField(null=True, blank=True)
    # When the lead became a paying customer
    converted_at   = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} — {self.status}"

    @property
    def is_converted(self):
        """Returns True if lead became a customer."""
        return self.status == 'converted'

    @property
    def is_lost(self):
        """Returns True if lead was lost."""
        return self.status == 'lost'


class Equipment(models.Model):
    """
    Tracks all physical assets owned by the business.
    Includes routers, access points, cables, switches
    and any other hardware used to run the WiFi service.
    Helps calculate total investment and track
    depreciation of assets over time.
    """

    TYPE_CHOICES = [
        ('router',       'Router'),
        ('access_point', 'Access Point'),
        ('cable',        'Cable'),
        ('switch',       'Switch'),
        ('other',        'Other'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),  # In stock, not yet deployed
        ('in_use',    'In Use'),     # Currently deployed
        ('faulty',    'Faulty'),     # Broken, needs repair
        ('retired',   'Retired'),    # Decommissioned
    ]

    # ── Equipment Details ──────────────────────────────
    # Category of equipment
    equipment_type  = models.CharField(
                          max_length=20,
                          choices=TYPE_CHOICES,
                          default='router'
                      )
    # Friendly name e.g. "Main Office Router"
    name            = models.CharField(max_length=200)
    # Device model e.g. "MikroTik hAP ac2"
    model           = models.CharField(max_length=200, blank=True)
    # Manufacturer serial number for warranty claims
    serial_number   = models.CharField(max_length=200, blank=True)
    # Current operational state
    status          = models.CharField(
                          max_length=15,
                          choices=STATUS_CHOICES,
                          default='available'
                      )

    # ── Purchase Information ───────────────────────────
    # When equipment was bought
    purchase_date   = models.DateField(null=True, blank=True)
    # How much it cost — feeds into investment calculations
    purchase_price  = models.DecimalField(
                          max_digits=10,
                          decimal_places=2,
                          null=True,
                          blank=True
                      )
    # Who sold it e.g. "Roke Telecom", "Jumia"
    vendor          = models.CharField(max_length=200, blank=True)
    # When warranty expires — used for maintenance alerts
    warranty_expiry = models.DateField(null=True, blank=True)

    # ── Location & Assignment ──────────────────────────
    # Where this equipment is deployed
    location        = models.CharField(max_length=200, blank=True)
    # Who is responsible for this equipment
    assigned_to     = models.CharField(max_length=200, blank=True)

    # ── Notes ──────────────────────────────────────────
    notes           = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.equipment_type} — {self.status}"

    @property
    def is_under_warranty(self):
        """Returns True if equipment is still under warranty."""
        from django.utils import timezone
        if self.warranty_expiry:
            return timezone.now().date() <= self.warranty_expiry
        return False

    @property
    def warranty_status(self):
        """Returns warranty status as readable string."""
        if not self.warranty_expiry:
            return 'No Warranty'
        if self.is_under_warranty:
            return f'Valid until {self.warranty_expiry}'
        return 'Expired'


class Advertisement(models.Model):
    """
    Manages advertisements displayed on the captive portal.
    Local businesses can pay to show ads to WiFi users
    while they are on the payment page.
    Ads can be scheduled by day and time, with
    impression limits and priority control.
    """

    AD_TYPE_CHOICES = [
        ('banner', 'Banner Image'),
        ('video',  'Video'),
        ('text',   'Text Ad'),
    ]

    # ── Basic Information ──────────────────────────────
    # Name of the advertisement
    title            = models.CharField(max_length=200)
    # Type of ad content
    ad_type          = models.CharField(
                           max_length=10,
                           choices=AD_TYPE_CHOICES,
                           default='banner'
                       )
    # Internal note about this ad
    description      = models.TextField(blank=True)
    # Whether this ad is currently active on the portal
    is_active        = models.BooleanField(default=True)

    # ── Media Content ──────────────────────────────────
    # The actual image or video file stored in media/ads/
    media_file       = models.FileField(
                           upload_to='ads/',
                           null=True,
                           blank=True
                       )
    # Where customer goes if they click the ad
    click_url        = models.URLField(blank=True)
    # How many seconds this ad shows before rotating
    display_duration = models.IntegerField(
                           default=10,
                           help_text='Seconds before rotating to next ad'
                       )

    # ── Scheduling ─────────────────────────────────────
    # When ad starts showing — null means immediately
    start_date       = models.DateTimeField(null=True, blank=True)
    # When ad stops showing — null means indefinitely
    end_date         = models.DateTimeField(null=True, blank=True)
    # List of days ad is active e.g. ["mon","tue","wed"]
    active_days      = models.JSONField(default=list, blank=True)
    # Daily start time — null means all day
    active_from      = models.TimeField(null=True, blank=True)
    # Daily end time — null means all day
    active_until     = models.TimeField(null=True, blank=True)

    # ── Rotation & Limits ──────────────────────────────
    # Higher number means this ad shows more often (0-100)
    priority              = models.IntegerField(default=0)
    # Used for random selection when ads have same priority
    weight                = models.IntegerField(default=1)
    # Stop showing after this many total views — null means unlimited
    max_impressions       = models.IntegerField(null=True, blank=True)
    # Maximum views per day — null means unlimited
    max_daily_impressions = models.IntegerField(null=True, blank=True)
    # Running total of how many times this ad has been shown
    total_impressions     = models.IntegerField(default=0)
    # Counter for today's views — resets at midnight
    daily_impressions     = models.IntegerField(default=0)
    # Used to detect when to reset the daily counter
    last_impression_date  = models.DateField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        # Show highest priority ads first
        ordering = ['-priority', 'weight']

    def __str__(self):
        return f"{self.title} — {self.ad_type}"

    @property
    def is_expired(self):
        """Returns True if ad has passed its end date."""
        from django.utils import timezone
        if self.end_date:
            return timezone.now() >= self.end_date
        return False

    @property
    def has_reached_limit(self):
        """Returns True if ad has reached max impressions."""
        if self.max_impressions:
            return self.total_impressions >= self.max_impressions
        return False


class Message(models.Model):
    """
    Tracks all SMS and WhatsApp messages sent to customers.
    Used for payment confirmations, session expiry warnings,
    voucher delivery and promotional communications.
    Stores the full message history for audit purposes.
    """

    CHANNEL_CHOICES = [
        ('sms',      'SMS'),       # Standard text message
        ('whatsapp', 'WhatsApp'),  # WhatsApp message
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),  # Queued but not yet sent
        ('sent',    'Sent'),     # Successfully delivered
        ('failed',  'Failed'),   # Delivery failed
    ]

    # ── Message Details ────────────────────────────────
    # Whether this goes via SMS or WhatsApp
    channel      = models.CharField(
                       max_length=10,
                       choices=CHANNEL_CHOICES,
                       default='sms'
                   )
    # Recipient's phone number with country code
    phone_number = models.CharField(max_length=15)
    # The actual message content
    message      = models.TextField()
    # Current delivery state
    status       = models.CharField(
                       max_length=10,
                       choices=STATUS_CHOICES,
                       default='pending'
                   )

    # ── Linked Records ─────────────────────────────────
    # Links message to a customer if available
    customer     = models.ForeignKey(
                       Customer,
                       on_delete=models.SET_NULL,
                       null=True,
                       blank=True
                   )

    # ── Response ───────────────────────────────────────
    # Error details if sending failed — useful for debugging
    error_message = models.TextField(blank=True)
    # Exact datetime when message was successfully sent
    sent_at       = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.channel} to {self.phone_number} — {self.status}"


class Feedback(models.Model):
    """
    Stores customer ratings and comments about their
    WiFi experience. Shown to customers on the connected
    page after their session starts.
    Used in analytics to track service quality and
    identify areas for improvement.
    """

    # ── Rating ─────────────────────────────────────────
    # Star rating from 1 to 5
    rating      = models.IntegerField(
                      choices=[
                          (1, '1 Star — Very Poor'),
                          (2, '2 Stars — Poor'),
                          (3, '3 Stars — Average'),
                          (4, '4 Stars — Good'),
                          (5, '5 Stars — Excellent'),
                      ]
                  )
    # Optional written feedback from customer
    comment     = models.TextField(blank=True)

    # ── Linked Records ─────────────────────────────────
    # Which device submitted this feedback
    device      = models.ForeignKey(
                      Device,
                      on_delete=models.CASCADE
                  )
    # Which WiFi session this feedback is about
    session     = models.ForeignKey(
                      WiFiSession,
                      on_delete=models.SET_NULL,
                      null=True,
                      blank=True
                  )
    # Which registered customer submitted this
    customer    = models.ForeignKey(
                      Customer,
                      on_delete=models.SET_NULL,
                      null=True,
                      blank=True
                  )

    # ── Timestamps ─────────────────────────────────────
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating} stars — {self.device.mac_address}"

    @property
    def is_positive(self):
        """4 or 5 stars is considered positive feedback."""
        return self.rating >= 4

    @property
    def is_negative(self):
        """1 or 2 stars is considered negative feedback."""
        return self.rating <= 2
    

class SystemSettings(models.Model):
    """
    Singleton model — only one record exists.
    Stores all system-wide configuration.
    """

    # ── Business Info ──────────────────────────────────
    business_name    = models.CharField(max_length=100, default='Kevid Tech')
    support_phone    = models.CharField(max_length=20, blank=True, default='')
    support_email    = models.EmailField(blank=True, default='')
    support_whatsapp = models.CharField(max_length=20, blank=True, default='')
    portal_url       = models.CharField(max_length=200, blank=True, default='')
    callback_url     = models.CharField(max_length=200, blank=True, default='')
    logo             = models.ImageField(upload_to='settings/', null=True, blank=True)

    # ── Portal Appearance ──────────────────────────────
    brand_color      = models.CharField(max_length=10, default='#2563eb')
    portal_font      = models.CharField(max_length=50, default='Inter')
    welcome_message  = models.TextField(blank=True, default='')
    footer_text      = models.TextField(blank=True, default='')
    terms_conditions = models.TextField(blank=True, default='')

    # ── Free Trial ─────────────────────────────────────
    free_trial_enabled  = models.BooleanField(default=True)
    free_trial_duration = models.IntegerField(default=30)
    free_trial_unit     = models.CharField(
                              max_length=10,
                              choices=[('minutes', 'Minutes'), ('hours', 'Hours')],
                              default='minutes'
                          )

    # ── Network ────────────────────────────────────────
    default_router_ip   = models.CharField(max_length=20, default='192.168.88.1')
    hotspot_network     = models.CharField(max_length=20, default='192.168.88.0/24')

    # ── Payments ───────────────────────────────────────
    mtn_collection_number    = models.CharField(max_length=20, blank=True, default='')
    mtn_api_key              = models.CharField(max_length=200, blank=True, default='')
    airtel_collection_number = models.CharField(max_length=20, blank=True, default='')
    airtel_api_key           = models.CharField(max_length=200, blank=True, default='')

    # ── SMS ────────────────────────────────────────────
    sms_enabled              = models.BooleanField(default=False)
    at_username              = models.CharField(max_length=100, blank=True, default='')
    at_api_key               = models.CharField(max_length=200, blank=True, default='')
    sms_sender_id            = models.CharField(max_length=20, blank=True, default='')
    sms_payment_template     = models.TextField(
                                   blank=True,
                                   default='Hi {name}, your payment of UGX {amount} was received. You now have {duration} of internet access. Thank you!'
                               )
    sms_expiry_template      = models.TextField(
                                   blank=True,
                                   default='Hi {name}, your internet session expires in 10 minutes. Visit the portal to renew.'
                               )
    sms_voucher_template     = models.TextField(
                                   blank=True,
                                   default='Your WiFi voucher code is: {code}. Valid for {duration}. Enjoy!'
                               )

    # ── WhatsApp ───────────────────────────────────────
    wa_enabled    = models.BooleanField(default=False)
    wa_number     = models.CharField(max_length=20, blank=True, default='')
    wa_token      = models.CharField(max_length=200, blank=True, default='')

    # ── Security ───────────────────────────────────────
    session_timeout     = models.IntegerField(default=30)
    max_login_attempts  = models.IntegerField(default=5)
    require_https       = models.BooleanField(default=False)
    log_activity        = models.BooleanField(default=True)

    # ── Timestamps ─────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Settings'

    def __str__(self):
        return f"System Settings — {self.business_name}"

    @classmethod
    def get_settings(cls):
        """
        Returns the single settings record.
        Creates it if it doesn't exist.
        """
        settings, created = cls.objects.get_or_create(id=1)
        return settings