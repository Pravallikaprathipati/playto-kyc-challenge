from django.core.management.base import BaseCommand
from django.utils import timezone
from kyc.models import User, KYCSubmission


class Command(BaseCommand):
    help = 'Seed basic test data: two merchants and one reviewer.'

    def handle(self, *args, **options):
        reviewer, _ = User.objects.get_or_create(
            username='reviewer',
            defaults={'email': 'reviewer@playto.test', 'role': User.REVIEWER, 'is_staff': True},
        )
        if reviewer.pk and not reviewer.has_usable_password():
            reviewer.set_password('password')
            reviewer.save()

        merchant_draft, _ = User.objects.get_or_create(
            username='merchant_draft',
            defaults={'email': 'merchant_draft@playto.test', 'role': User.MERCHANT},
        )
        if not merchant_draft.has_usable_password():
            merchant_draft.set_password('password')
            merchant_draft.save()
        KYCSubmission.objects.get_or_create(
            merchant=merchant_draft,
            state=KYCSubmission.DRAFT,
            personal_name='Draft Merchant',
            business_name='Draft Co',
            defaults={'personal_email': 'draft@playto.test', 'personal_phone': '+911234567890'},
        )

        merchant_review, _ = User.objects.get_or_create(
            username='merchant_under_review',
            defaults={'email': 'merchant_under_review@playto.test', 'role': User.MERCHANT},
        )
        if not merchant_review.has_usable_password():
            merchant_review.set_password('password')
            merchant_review.save()
        KYCSubmission.objects.get_or_create(
            merchant=merchant_review,
            state=KYCSubmission.UNDER_REVIEW,
            personal_name='Review Merchant',
            business_name='Review Co',
            defaults={'personal_email': 'review@playto.test', 'personal_phone': '+919876543210', 'submitted_at': timezone.now()},
        )

        self.stdout.write(self.style.SUCCESS('Seed data created successfully.'))
