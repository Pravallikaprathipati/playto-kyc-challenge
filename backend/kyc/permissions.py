from rest_framework import permissions
from .models import KYCSubmission


class IsReviewerOrSubmissionOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_reviewer:
            return True
        return obj.merchant == request.user


class IsMerchantOrReviewer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_reviewer or request.user.is_merchant
        )


class CanEditSubmission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_reviewer:
            return True
        return obj.merchant == request.user and obj.state in [
            KYCSubmission.DRAFT,
            KYCSubmission.MORE_INFO_REQUESTED,
        ]
