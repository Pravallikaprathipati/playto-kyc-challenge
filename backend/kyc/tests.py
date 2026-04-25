from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import User, KYCSubmission


class KYCStateMachineTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(
            username='merchant', password='password', role=User.MERCHANT
        )
        self.reviewer = User.objects.create_user(
            username='reviewer', password='password', role=User.REVIEWER
        )
        self.submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            personal_name='Test Merchant',
            business_name='Test Business',
        )

    def test_illegal_state_transition_rejected_to_draft(self):
        self.client.force_authenticate(user=self.reviewer)
        # Move submission to rejected first
        self.submission.state = KYCSubmission.REJECTED
        self.submission.save()
        url = reverse('submission-review', kwargs={'pk': self.submission.pk})
        response = self.client.post(url, {'action': 'start_review'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Illegal transition', response.data['detail'])

    def test_merchant_cannot_access_other_merchant_submission(self):
        other = User.objects.create_user(
            username='merchant2', password='password', role=User.MERCHANT
        )
        self.client.force_authenticate(user=other)
        url = reverse('submission-detail', kwargs={'pk': self.submission.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
