from django.db.models import F, DurationField, ExpressionWrapper
from django.db.models.functions import Now
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken

from .models import KYCSubmission, KYCDocument, Notification
from .serializers import (
    UserRegistrationSerializer,
    KYCSubmissionSerializer,
    KYCDocumentSerializer,
    ReviewActionSerializer,
    ReviewerMetricsSerializer,
)
from .permissions import IsReviewerOrSubmissionOwner, CanEditSubmission


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer


class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        return Response({'token': token.key, 'user_id': token.user_id, 'role': token.user.role})


class SubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = KYCSubmissionSerializer
    permission_classes = [IsAuthenticated, IsReviewerOrSubmissionOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_reviewer:
            return KYCSubmission.objects.all().order_by('created_at')
        return KYCSubmission.objects.filter(merchant=user).order_by('created_at')

    def perform_create(self, serializer):
        serializer.save()

    def get_permissions(self):
        if self.action in ['create']:
            return [IsAuthenticated()]
        return [permission() for permission in self.permission_classes]

    def partial_update(self, request, *args, **kwargs):
        submission = self.get_object()
        if not request.user.is_reviewer and submission.merchant != request.user:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        submission = self.get_object()
        if submission.merchant != request.user:
            return Response({'detail': 'Only the merchant may submit this application.'}, status=status.HTTP_403_FORBIDDEN)
        if submission.state not in [KYCSubmission.DRAFT, KYCSubmission.MORE_INFO_REQUESTED]:
            return Response({'detail': 'Submission cannot be submitted from its current state.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            submission.transition_to(KYCSubmission.SUBMITTED, actor=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(submission).data)

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        if not request.user.is_reviewer:
            return Response({'detail': 'Only reviewers may perform review actions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission = self.get_object()
        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')
        if action == 'start_review':
            next_state = KYCSubmission.UNDER_REVIEW
        elif action == 'approve':
            next_state = KYCSubmission.APPROVED
        elif action == 'reject':
            next_state = KYCSubmission.REJECTED
        elif action == 'request_more_info':
            next_state = KYCSubmission.MORE_INFO_REQUESTED
        else:
            return Response({'detail': 'Unknown action.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            submission.transition_to(next_state, actor=request.user, reason=reason)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if next_state in [KYCSubmission.REJECTED, KYCSubmission.MORE_INFO_REQUESTED]:
            submission.review_reason = reason
            submission.save(update_fields=['review_reason'])
        return Response(self.get_serializer(submission).data)


class KYCDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = KYCDocumentSerializer
    permission_classes = [IsAuthenticated, IsReviewerOrSubmissionOwner]

    def get_queryset(self):
        submission_id = self.kwargs.get('submission_pk')
        return KYCDocument.objects.filter(submission_id=submission_id)

    def perform_create(self, serializer):
        submission = KYCSubmission.objects.get(pk=self.kwargs['submission_pk'])
        if submission.merchant != self.request.user and not self.request.user.is_reviewer:
            raise PermissionDenied('Only the merchant can upload documents for this submission.')
        serializer.save(submission=submission)


class ReviewerDashboardView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReviewerMetricsSerializer

    def get(self, request):
        if not request.user.is_reviewer:
            return Response({'detail': 'Only reviewers may access reviewer metrics.'}, status=status.HTTP_403_FORBIDDEN)
        queue = KYCSubmission.objects.filter(state__in=[
            KYCSubmission.SUBMITTED,
            KYCSubmission.UNDER_REVIEW,
        ])
        age_expr = ExpressionWrapper(Now() - F('submitted_at'), output_field=DurationField())
        queue = queue.annotate(age=age_expr).order_by('submitted_at')
        seconds = 0
        total = queue.count()
        for item in queue:
            seconds += item.age.total_seconds()
        average_minutes = (seconds / total / 60) if total else 0.0
        last_week = timezone.now() - timezone.timedelta(days=7)
        approved_count = KYCSubmission.objects.filter(
            state=KYCSubmission.APPROVED,
            updated_at__gte=last_week,
        ).count()
        total_decisions = KYCSubmission.objects.filter(
            state__in=[KYCSubmission.APPROVED, KYCSubmission.REJECTED],
            updated_at__gte=last_week,
        ).count()
        approval_rate = (approved_count / total_decisions * 100) if total_decisions else 0.0
        payload = {
            'submissions_in_queue': total,
            'average_time_in_queue_minutes': round(average_minutes, 1),
            'approval_rate_last_7_days': round(approval_rate, 1),
        }
        return Response(payload)
