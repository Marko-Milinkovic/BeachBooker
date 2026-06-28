from django.contrib import admin

from core.models import (
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
    list_display = ("email", "first_name", "last_name", "role", "created_at")
    search_fields = ("email", "first_name", "last_name")


admin.site.register(Amenity)
admin.site.register(BeachBar)
admin.site.register(SunbedCategory)
admin.site.register(Sunbed)
admin.site.register(Reservation)
admin.site.register(Bundle)
admin.site.register(Review)
