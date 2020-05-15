from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q, F
from django.core.exceptions import ValidationError
import stripe
import decimal
import uuid


class Account(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    default_stripe_payment_method_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return str(self.user)

    @property
    def balance(self):
        return self.ledgeritem_set\
            .filter(state=LedgerItem.STATE_COMPLETED)\
            .aggregate(balance=models.Sum('amount'))\
            .get('balance') or decimal.Decimal(0)

    @property
    def pending_balance(self):
        return self.ledgeritem_set\
            .filter(Q(state=LedgerItem.STATE_PENDING) | Q(state=LedgerItem.STATE_PROCESSING))\
            .aggregate(balance=models.Sum('amount'))\
            .get('balance') or decimal.Decimal(0)

    def get_stripe_id(self):
        if self.stripe_customer_id:
            return self.stripe_customer_id

        customer = stripe.Customer.create()
        customer_id = customer['id']
        self.stripe_customer_id = customer_id
        self.save()
        return customer_id


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(user=instance)
    instance.account.save()


class LedgerItem(models.Model):
    STATE_PENDING = "P"
    STATE_PROCESSING = "S"
    STATE_FAILED = "F"
    STATE_COMPLETED = "C"
    STATES = (
        (STATE_PENDING, "Pending"),
        (STATE_PROCESSING, "Processing"),
        (STATE_FAILED, "Failed"),
        (STATE_COMPLETED, "Completed"),
    )

    TYPE_CHARGE = "B"
    TYPE_CARD = "C"
    TYPE_BACS = "F"
    TYPE_SOURCES = "S"
    TYPES = (
        (TYPE_CHARGE, "Charge"),
        (TYPE_CARD, "Card"),
        (TYPE_BACS, "BACS/Faster payments/SEPA"),
        (TYPE_SOURCES, "Sources"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    descriptor = models.CharField(max_length=255)
    amount = models.DecimalField(decimal_places=2, max_digits=9, default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=1, choices=STATES, default=STATE_PENDING)
    type = models.CharField(max_length=1, choices=TYPES, default=TYPE_CHARGE)
    type_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    @property
    def balance_at(self):
        queryset = self.account.ledgeritem_set \
            .filter(timestamp__lte=self.timestamp)

        if self.state not in (self.STATE_PENDING, self.STATE_PROCESSING):
            queryset = queryset.filter(state=self.STATE_COMPLETED)
        else:
            queryset = queryset.filter(state__in=(self.STATE_COMPLETED, self.STATE_PENDING, self.STATE_PROCESSING))

        return queryset \
            .aggregate(balance=models.Sum('amount')) \
            .get('balance') or decimal.Decimal(0)


class ExchangeRate(models.Model):
    timestamp = models.DateTimeField()
    currency = models.CharField(max_length=3)
    rate = models.DecimalField(decimal_places=7, max_digits=20)

    def __str__(self):
        return self.currency

    @classmethod
    def get_rate(cls, from_currency, to_currency):
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return 1

        from_obj = cls.objects.get(currency=from_currency)
        to_obj = cls.objects.get(currency=to_currency)

        return to_obj.rate / from_obj.rate


class RecurringPlan(models.Model):
    TYPE_RECURRING = "R"
    TYPE_METERED = "M"
    TYPES = (
        (TYPE_RECURRING, "Recurring"),
        (TYPE_METERED, "Metered")
    )

    INTERVAL_DAY = "D"
    INTERVAL_WEEK = "W"
    INTERVAL_MONTH = "M"
    INTERVALS = (
        (INTERVAL_DAY, "Day"),
        (INTERVAL_MONTH, "Month"),
        (INTERVAL_WEEK, "Week")
    )

    TIERS_VOLUME = "V"
    TIERS_GRADUATED = "G"
    TIERS = (
        (TIERS_VOLUME, "Volume"),
        (TIERS_GRADUATED, "Graduated")
    )

    AGGREGATION_MAX = "M"
    AGGREGATION_SUM = "S"
    AGGREGATION_LAST_EVER = "E"
    AGGREGATION_LAST_PERIOD = "P"
    AGGREGATIONS = (
        (AGGREGATION_MAX, "Maximum value over period"),
        (AGGREGATION_SUM, "Sum over period"),
        (AGGREGATION_LAST_EVER, "Last ever value"),
        (AGGREGATION_LAST_PERIOD, "Last value in period"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    unit_label = models.CharField(max_length=255)
    billing_interval_value = models.PositiveSmallIntegerField()
    billing_interval_unit = models.CharField(max_length=1, choices=INTERVALS)
    billing_type = models.CharField(max_length=1, choices=TYPES)
    tiers_type = models.CharField(max_length=1, choices=TIERS)
    aggregation_type = models.CharField(max_length=1, choices=AGGREGATIONS, blank=True, null=True)

    def clean(self):
        if self.billing_type == self.TYPE_RECURRING and self.aggregation_type is not None:
            raise ValidationError("Aggregation type does not apply to recurring types")
        elif self.billing_type == self.TYPE_METERED and self.aggregation_type is None:
            raise ValidationError("Aggregation type is required for metered types")

    def calculate_charge(self, units: int) -> decimal.Decimal:
        if self.tiers_type == self.TIERS_VOLUME:
            tier = self.recurringplantier_set.filter(last_unit__lte=units)\
                .order_by(F('last_unit').desc(nulls_last=True)).first()
            return (tier.price_per_unit * decimal.Decimal(units)) + tier.flat_fee
        elif self.tiers_type == self.TIERS_GRADUATED:
            tiers = self.recurringplantier_set.order_by(F('last_unit').asc(nulls_last=True))
            total = decimal.Decimal(0)
            for tier in tiers:
                if tier.last_unit:
                    nums = min(units, tier.last_unit)
                else:
                    nums = units
                total += (tier.price_per_unit * decimal.Decimal(nums)) + tier.flat_fee
                units -= nums
                if units <= 0:
                    break
            return total

    def __str__(self):
        return self.name


class RecurringPlanTier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    plan = models.ForeignKey(RecurringPlan, on_delete=models.CASCADE)
    last_unit = models.PositiveIntegerField(blank=True, null=True)
    price_per_unit = models.DecimalField(decimal_places=14, max_digits=28)
    flat_fee = models.DecimalField(decimal_places=2, max_digits=9)

    class Meta:
        ordering = ['last_unit']


class Subscription(models.Model):
    STATE_ACTIVE = "A"
    STATE_PAST_DUE = "P"
    STATE_CANCELLED = "C"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    plan = models.ForeignKey(RecurringPlan, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    last_billed = models.DateTimeField()
    last_bill_attempted = models.DateTimeField()


class SubscriptionUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    usage_units = models.PositiveIntegerField()

    class Meta:
        ordering = ['-timestamp']
