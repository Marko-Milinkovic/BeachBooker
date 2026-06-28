from django.urls import path

from core.views import pages

urlpatterns = [
    path("", pages.index, name="index"),
]
