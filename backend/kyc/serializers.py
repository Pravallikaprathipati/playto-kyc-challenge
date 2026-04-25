from rest_framework import serializers
from django.utils import timezone
from .models import User, KYCSubmission, KYCDocument, Notification

ALLOWED_CONTENT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
MAX_FILE_SIZE = 5 * 1024 * 1024


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'role']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = ['id', 'doc_type', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']

    def validate_file(self, value):
        if value.content_type not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                'Unsupported file type. Only PDF, JPG, PNG files are allowed.'
            )
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError('File too large. Maximum size is 5 MB.')
        return value

    def validate(self, attrs):
        if self.instance and self.instance.submission.state not in [
            KYCSubmission.DRAFT,
            KYCSubmission.MORE_INFO_REQUESTED,
        ]:
            raise serializers.ValidationError(
                'Cannot upload documents once submission is submitted for review.'
            )
        return attrs


class KYCSubmissionSerializer(serializers.ModelSerializer):
    documents = KYCDocumentSerializer(many=True, read_only=True)
    state = serializers.CharField(read_only=True)
    is_at_risk = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = [
            'id',
            'state',
            'personal_name',
            'personal_email',
            'personal_phone',
            'business_name',
            'business_type',
            'expected_monthly_volume_usd',
            'review_reason',
            'documents',
            'created_at',
            'updated_at',
            'submitted_at',
            'is_at_risk',
        ]
        read_only_fields = ['id', 'state', 'created_at', 'updated_at', 'submitted_at', 'is_at_risk']

    def get_is_at_risk(self, obj):
        return obj.is_at_risk

    def validate(self, attrs):
        user = self.context['request'].user
        if self.instance and self.instance.merchant != user:
            raise serializers.ValidationError('You may only edit your own submission.')
        if self.instance and self.instance.state not in [
            KYCSubmission.DRAFT,
            KYCSubmission.MORE_INFO_REQUESTED,
        ]:
            raise serializers.ValidationError(
                'You can only edit details while the submission is draft or more information requested.'
            )
        return attrs

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def create(self, validated_data):
        merchant = self.context['request'].user
        submission = KYCSubmission.objects.create(merchant=merchant, **validated_data)
        return submission


class ReviewActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[
            ('start_review', 'Start Review'),
            ('approve', 'Approve'),
            ('reject', 'Reject'),
            ('request_more_info', 'Request More Info'),
        ]
    )
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        action = attrs['action']
        reason = attrs.get('reason', '').strip()
        if action in ['reject', 'request_more_info'] and not reason:
            raise serializers.ValidationError('A reason is required for reject or request_more_info.')
        return attrs


class ReviewerMetricsSerializer(serializers.Serializer):
    submissions_in_queue = serializers.IntegerField()
    average_time_in_queue_minutes = serializers.FloatField()
    approval_rate_last_7_days = serializers.FloatField()
