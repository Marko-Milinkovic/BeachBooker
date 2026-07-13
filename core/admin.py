from django.contrib import admin

from core.models import (
    AdminActionLog,
    Amenity,
    BeachBar,
    Bundle,
    Reservation,
    Review,
    Sunbed,
    SunbedCategory,
    User,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("email", "first_name", "last_name")


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    ordering = ("-created_at",)
    list_display = ("created_at", "admin", "action", "target_type", "target_id", "detail")
    list_filter = ("action",)
    search_fields = ("detail", "admin__email")


admin.site.register(Amenity)
admin.site.register(BeachBar)
admin.site.register(SunbedCategory)
admin.site.register(Sunbed)
admin.site.register(Reservation)
admin.site.register(Bundle)
admin.site.register(Review)
