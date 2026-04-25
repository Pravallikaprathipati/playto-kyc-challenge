from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    MERCHANT = 'merchant'
    REVIEWER = 'reviewer'
    ROLE_CHOICES = [
        (MERCHANT, 'Merchant'),
        (REVIEWER, 'Reviewer'),
    ]

    role = models.CharField(max_length=16, choices=ROLE_CHOICES)

    @property
    def is_reviewer(self):
        return self.role == self.REVIEWER

    @property
    def is_merchant(self):
        return self.role == self.MERCHANT


class KYCSubmission(models.Model):
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    MORE_INFO_REQUESTED = 'more_info_requested'

    STATE_CHOICES = [
        (DRAFT, 'Draft'),
        (SUBMITTED, 'Submitted'),
        (UNDER_REVIEW, 'Under Review'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (MORE_INFO_REQUESTED, 'More Info Requested'),
    ]

    TRANSITIONS = {
        DRAFT: [SUBMITTED],
        SUBMITTED: [UNDER_REVIEW],
        UNDER_REVIEW: [APPROVED, REJECTED, MORE_INFO_REQUESTED],
        MORE_INFO_REQUESTED: [SUBMITTED],
    }

    merchant = models.ForeignKey('User', related_name='submissions', on_delete=models.CASCADE)
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=DRAFT)
    personal_name = models.CharField(max_length=255, blank=True)
    personal_email = models.EmailField(blank=True)
    personal_phone = models.CharField(max_length=32, blank=True)
    business_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(max_length=128, blank=True)
    expected_monthly_volume_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    review_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def can_transition_to(self, next_state):
        return next_state in self.TRANSITIONS.get(self.state, [])

    def transition_to(self, next_state, actor=None, reason=None):
        if not self.can_transition_to(next_state):
            raise ValueError(
                f'Illegal transition from {self.state} to {next_state}'
            )
        previous = self.state
        self.state = next_state
        if next_state == self.SUBMITTED:
            self.submitted_at = timezone.now()
        self.save(update_fields=['state', 'submitted_at' if next_state == self.SUBMITTED else 'updated_at'])
        Notification.objects.create(
            merchant=self.merchant,
            event_type='state_changed',
            payload={
                'from': previous,
                'to': next_state,
                'actor': actor.username if actor else None,
                'reason': reason,
            },
        )

    @property
    def is_at_risk(self):
        if self.state not in {self.SUBMITTED, self.UNDER_REVIEW}:
            return False
        threshold = timezone.now() - timezone.timedelta(hours=24)
        # Use submitted_at if available (for submitted/under_review), otherwise created_at
        reference_time = self.submitted_at if self.submitted_at else self.created_at
        return reference_time < threshold


class KYCDocument(models.Model):
    PAN = 'pan'
    AADHAAR = 'aadhaar'
    BANK_STATEMENT = 'bank_statement'
    DOC_TYPES = [
        (PAN, 'PAN Card'),
        (AADHAAR, 'Aadhaar'),
        (BANK_STATEMENT, 'Bank Statement'),
    ]

    submission = models.ForeignKey(KYCSubmission, related_name='documents', on_delete=models.CASCADE)
    doc_type = models.CharField(max_length=32, choices=DOC_TYPES)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('submission', 'doc_type')


class Notification(models.Model):
    merchant = models.ForeignKey('User', related_name='notifications', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=64)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']
