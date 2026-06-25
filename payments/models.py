from django.db import models
from portal.models import Package, Device, Customer


class Order(models.Model):
    """
    Represents every payment attempt a customer makes.
    Created immediately when customer clicks PAY NOW —
    before even contacting MTN or Airtel.
    Tracks the full lifecycle of a payment from
    initiation to success or failure.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),   # Payment initiated, waiting for customer PIN
        ('success', 'Success'),   # Payment confirmed by MTN/Airtel callback
        ('failed',  'Failed'),    # Payment rejected or timed out
    ]

    PROVIDER_CHOICES = [
        ('mtn',    'MTN MoMo'),      # MTN Mobile Money
        ('airtel', 'Airtel Money'),  # Airtel Money
    ]

    # ── Relationships ──────────────────────────────────
    # The device that initiated this payment
    device       = models.ForeignKey(
                       Device,
                       on_delete=models.CASCADE
                   )
    # The package the customer chose to purchase
    package      = models.ForeignKey(
                       Package,
                       on_delete=models.CASCADE
                   )
    # The customer account if they are registered
    customer     = models.ForeignKey(
                       Customer,
                       on_delete=models.SET_NULL,
                       null=True,
                       blank=True
                   )

    # ── Payment Details ────────────────────────────────
    # Phone number the customer used to pay
    phone_number = models.CharField(max_length=15)
    # Amount charged — copied from package price at time of purchase
    amount       = models.DecimalField(max_digits=10, decimal_places=2)
    # Which mobile money provider was used
    provider     = models.CharField(
                       max_length=10,
                       choices=PROVIDER_CHOICES
                   )
    # Current state of this payment
    status       = models.CharField(
                       max_length=10,
                       choices=STATUS_CHOICES,
                       default='pending'
                   )

    # ── Reference IDs ──────────────────────────────────
    # Our own unique ID sent to MTN/Airtel to track this transaction
    reference_id  = models.CharField(max_length=100, unique=True)
    # The transaction ID returned by MTN/Airtel after payment
    momo_txn_id   = models.CharField(max_length=100, blank=True)

    # ── Router ─────────────────────────────────────────
    # Which router this order was initiated from
    # Used to grant internet access on the correct router
    router       = models.ForeignKey(
                       'network.MikroTikRouter',
                       on_delete=models.SET_NULL,
                       null=True,
                       blank=True,
                       related_name='orders'
                   )
    
    # ── Order Type ─────────────────────────────────────────
# Distinguishes between direct payments and voucher purchases
    order_type   = models.CharField(
                   max_length=10,
                   choices=[('payment', 'Payment'), ('voucher', 'Voucher')],
                   default='payment'
               )
    # ── Device IP Address ──────────────────────────────
    # IP address of the device at time of payment
    # Used by callbacks to create the WiFi session
    ip_address   = models.GenericIPAddressField(
                   null=True,
                   blank=True
               )
                   

    # ── Timestamps ─────────────────────────────────────
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)


    # Add this at the bottom of the Order model
    # after the updated_at field
    session = models.OneToOneField(
              'portal.WiFiSession',
              on_delete=models.SET_NULL,
              null=True,
              blank=True,
              related_name='order'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.reference_id} — {self.status}"


class Withdrawal(models.Model):
    """
    Represents a request by the admin to withdraw
    collected mobile money balance to their personal
    mobile money account.
    Uses email verification for security before
    processing the payout.
    """

    STATUS_CHOICES = [
        ('pending',   'Pending'),   # Request submitted, not yet processed
        ('completed', 'Completed'), # Money successfully sent
        ('failed',    'Failed'),    # Transfer failed
        ('cancelled', 'Cancelled'), # Admin cancelled the request
    ]

    # ── Withdrawal Details ─────────────────────────────
    # Amount to withdraw in UGX
    amount          = models.DecimalField(
                          max_digits=10,
                          decimal_places=2
                      )
    # Mobile money number to send money to
    mobile_number   = models.CharField(max_length=15)
    # Current state of the withdrawal
    status          = models.CharField(
                          max_length=10,
                          choices=STATUS_CHOICES,
                          default='pending'
                      )
    
    # Mobile money provider used for this withdrawal
    provider     = models.CharField(
                   max_length=20,
                   blank=True,
                   default=''
               )
    # Account holder name for verification
    account_name = models.CharField(
                   max_length=100,
                   blank=True,
                   default=''
               )

    # ── Reference & Notes ──────────────────────────────
    # Transaction reference from the mobile money provider
    reference       = models.CharField(max_length=100, blank=True)
    # Optional notes about this withdrawal
    notes           = models.TextField(blank=True)

    # ── Email Verification ─────────────────────────────
    # 6-digit code sent to admin email to confirm withdrawal
    verification_code    = models.CharField(max_length=10, blank=True)
    # When the verification code was sent — used to expire old codes
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    # Whether admin confirmed with the correct verification code
    verified             = models.BooleanField(default=False)

    # ── Completion ─────────────────────────────────────
    # Exact datetime when withdrawal was completed
    completed_at    = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal UGX {self.amount} — {self.status}"

    @property
    def is_pending(self):
        """Returns True if withdrawal is still pending."""
        return self.status == 'pending'

    @property
    def is_completed(self):
        """Returns True if withdrawal completed successfully."""
        return self.status == 'completed'


class VoucherAgent(models.Model):
    """
    Represents a reseller/agent who sells WiFi vouchers
    on behalf of the business. Agents can be shopkeepers,
    market vendors, or any trusted individual who
    pre-purchases voucher batches and sells them to customers.
    Each agent earns a commission per voucher sold.
    """

    STATUS_CHOICES = [
        ('active',   'Active'),    # Agent is actively selling
        ('inactive', 'Inactive'),  # Agent is temporarily suspended
    ]

    COMMISSION_TYPE_CHOICES = [
        ('percentage', 'Percentage (%)'),  # Earn % of voucher price
        ('fixed',      'Fixed Amount'),    # Earn fixed UGX per sale
    ]

    # ── Agent Information ──────────────────────────────
    # Agent's full name
    name             = models.CharField(max_length=100)
    # Agent's phone number for contact
    phone            = models.CharField(max_length=15, blank=True)
    # Physical location of agent's shop or stall
    location         = models.CharField(max_length=200, blank=True)
    # Whether this agent is currently active
    status           = models.CharField(
                           max_length=10,
                           choices=STATUS_CHOICES,
                           default='active'
                       )

    # ── Commission Configuration ───────────────────────
    # Whether commission is percentage or fixed amount
    commission_type  = models.CharField(
                           max_length=15,
                           choices=COMMISSION_TYPE_CHOICES,
                           default='percentage'
                       )
    # The actual commission value — e.g. 10 for 10% or 500 for UGX 500
    commission_value = models.DecimalField(
                           max_digits=5,
                           decimal_places=2,
                           default=0
                       )

    # ── Notes ──────────────────────────────────────────
    notes      = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.location}"

    @property
    def commission_display(self):
        """Returns commission as readable string."""
        if self.commission_type == 'percentage':
            return f"{self.commission_value}%"
        return f"UGX {self.commission_value}"


class Voucher(models.Model):
    """
    Represents a prepaid voucher code that a customer
    can purchase and redeem for internet access.
    Vouchers are an alternative to direct mobile money
    payments — useful for walk-in cash sales and
    agent reselling.
    Each voucher gives access to a specific package
    for a specific duration.
    """

    STATUS_CHOICES = [
        ('available', 'Available'),  # Not yet used
        ('used',      'Used'),       # Already redeemed
        ('expired',   'Expired'),    # Past expiry date
        ('giveaway',  'Giveaway'),   # Free voucher, not counted as revenue
    ]

    SALE_TYPE_CHOICES = [
        ('online',   'Online Sale'),   # Sold via mobile money on portal
        ('walk_in',  'Walk-in Sale'),  # Sold in person for cash
        ('agent',    'Agent Sale'),    # Sold by a registered agent
        ('giveaway', 'Giveaway'),      # Given away free
    ]

    # ── Voucher Details ────────────────────────────────
    # The unique alphanumeric code customer enters e.g. "A4KX92"
    code            = models.CharField(max_length=20, unique=True)
    # Which package this voucher gives access to
    package         = models.ForeignKey(
                          Package,
                          on_delete=models.CASCADE
                      )
    # Current state of this voucher
    status          = models.CharField(
                          max_length=10,
                          choices=STATUS_CHOICES,
                          default='available'
                      )
    # Whether this is a free giveaway voucher
    is_giveaway     = models.BooleanField(default=False)

    # ── Batch Information ──────────────────────────────
    # Groups vouchers generated together e.g. "Morning-Batch-1"
    batch_reference = models.CharField(max_length=100, blank=True)
    # Optional letter prefix on the code e.g. "A" makes codes like "A4KX92"
    prefix          = models.CharField(max_length=5, blank=True)

    # ── Sale Information ───────────────────────────────
    # How this voucher was sold
    sale_type       = models.CharField(
                          max_length=10,
                          choices=SALE_TYPE_CHOICES,
                          default='walk_in'
                      )
    # Which agent sold this voucher — null if sold online or walk-in
    agent           = models.ForeignKey(
                          VoucherAgent,
                          on_delete=models.SET_NULL,
                          null=True,
                          blank=True
                      )
    # Actual price the voucher was sold for
    price_sold      = models.DecimalField(
                          max_digits=10,
                          decimal_places=2,
                          default=0
                      )

    # ── Usage Information ──────────────────────────────
    # Which device redeemed this voucher
    used_by_device   = models.ForeignKey(
                           Device,
                           on_delete=models.SET_NULL,
                           null=True,
                           blank=True
                       )
    # Which customer redeemed this voucher
    used_by_customer = models.ForeignKey(
                           Customer,
                           on_delete=models.SET_NULL,
                           null=True,
                           blank=True
                       )
    # Exact datetime when voucher was redeemed
    used_at         = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} — {self.package.name} — {self.status}"

    @property
    def is_available(self):
        """Returns True if voucher has not been used."""
        return self.status == 'available'

    @property
    def value(self):
        """Returns the package price as the voucher face value."""
        return self.package.price