from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, KYCSubmission, KYCDocument, Notification


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']


@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'state', 'created_at']
    list_filter = ['state']
    search_fields = ['merchant__username', 'business_name']


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'submission', 'doc_type', 'uploaded_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'event_type', 'timestamp']
