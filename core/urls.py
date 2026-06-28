from django.urls import path

from core.views import api, pages

urlpatterns = [
    path("", pages.index, name="index"),
    path("explore/", pages.explore, name="explore"),
    path("bars/<int:bar_id>/", pages.beach_bar, name="beach_bar"),
    path("api/bars/<int:bar_id>/sunbeds/", api.bar_sunbeds, name="api_bar_sunbeds"),
]
