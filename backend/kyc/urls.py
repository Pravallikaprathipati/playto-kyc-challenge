from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    CustomAuthToken,
    SubmissionViewSet,
    KYCDocumentViewSet,
    ReviewerDashboardView,
)

router = DefaultRouter()
router.register(r'submissions', SubmissionViewSet, basename='submission')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/token/', CustomAuthToken.as_view(), name='token'),
    path('reviewer/dashboard/', ReviewerDashboardView.as_view(), name='reviewer-dashboard'),
    path('submissions/<int:submission_pk>/documents/', KYCDocumentViewSet.as_view({
        'get': 'list',
        'post': 'create',
    }), name='submission-documents'),
    path('', include(router.urls)),
]
