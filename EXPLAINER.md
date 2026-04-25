# EXPLAINER

## 1. The State Machine

The state machine lives in `backend/kyc/models.py` inside the `KYCSubmission` model.

Function:
```python
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
```

Illegal transitions are blocked by `can_transition_to` and raised as `ValueError` in `transition_to`. The API catches this and returns a 400.

## 2. The Upload

File uploads are validated in `backend/kyc/serializers.py` in `KYCDocumentSerializer.validate_file`.

```python
    def validate_file(self, value):
        if value.content_type not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                'Unsupported file type. Only PDF, JPG, PNG files are allowed.'
            )
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError('File too large. Maximum size is 5 MB.')
        return value
```

If someone sends a 50 MB file, the serializer rejects it and returns a validation error with `File too large. Maximum size is 5 MB.`

## 3. The Queue

The reviewer dashboard query is in `backend/kyc/views.py`:

```python
queue = KYCSubmission.objects.filter(state__in=[
    KYCSubmission.SUBMITTED,
    KYCSubmission.UNDER_REVIEW,
])
age_expr = ExpressionWrapper(Now() - F('created_at'), output_field=DurationField())
queue = queue.annotate(age=age_expr).order_by('created_at')
```

This query returns queue submissions sorted oldest first and computes the current age dynamically to mark SLA risk without storing stale flags.

## 4. The Auth

Merchant access control is enforced in `backend/kyc/permissions.py` and `backend/kyc/views.py`.

Example check in `IsReviewerOrSubmissionOwner`:
```python
    def has_object_permission(self, request, view, obj):
        if request.user.is_reviewer:
            return True
        return obj.merchant == request.user
```

A merchant can only access submissions where `obj.merchant == request.user`.

## 5. The AI Audit

An AI suggestion initially created view permission logic that used `PermissionError` inside DRF view code. I replaced it with Django REST Framework-friendly permission handling and explicit `PermissionDenied` to ensure the API returns proper HTTP errors.

```python
if submission.merchant != self.request.user and not self.request.user.is_reviewer:
    raise PermissionDenied('Only the merchant can upload documents for this submission.')
```

I audited this to avoid a raw Python exception leaking into DRF response handling.
