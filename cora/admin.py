from django.contrib import admin
from .models import ApiToken, ColaApplication, LabelImage


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    """ApiToken admin with read-only access for non-superusers."""

    list_display = ['name', 'prefix', 'created_by', 'scopes', 'created_at', 'expires_at', 'revoked_at', 'last_used_at']
    list_filter = ['scopes', 'created_at', 'expires_at', 'revoked_at']
    search_fields = ['name', 'prefix', 'created_by__username']

    def get_readonly_fields(self, request, obj=None):
        """Non-superusers can only view, not edit."""
        if not request.user.is_superuser:
            return [f.name for f in self.model._meta.fields if f.name != 'id']
        return ['created_at', 'last_used_at', 'prefix']

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ColaApplication)
class ColaApplicationAdmin(admin.ModelAdmin):
    list_display = ['brand_name', 'ttb_id', 'applicant_name', 'product_type', 'status']
    list_filter = ['status', 'product_type']
    search_fields = ['ttb_id', 'brand_name', 'applicant_name']


@admin.register(LabelImage)
class LabelImageAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'label_type', 'ocr_status', 'created_at']
    list_filter = ['label_type', 'ocr_status']
    search_fields = ['file_name']