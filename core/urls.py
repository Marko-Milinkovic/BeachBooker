from django.urls import path

from core.views import pages

urlpatterns = [
    path("", pages.index, name="index"),
    path("explore/", pages.explore, name="explore"),
    path("bars/<int:bar_id>/", pages.beach_bar, name="beach_bar"),
]
