from django.urls import path

from core.views import api, auth, pages

urlpatterns = [
    path("", pages.index, name="index"),
    path("explore/", pages.explore, name="explore"),
    path("bars/<int:bar_id>/", pages.beach_bar, name="beach_bar"),
    path("api/bars/<int:bar_id>/sunbeds/", api.bar_sunbeds, name="api_bar_sunbeds"),
    path("api/bars/<int:bar_id>/book/", api.book_sunbeds_api, name="api_book_sunbeds"),
    path(
        "api/reservations/<int:reservation_id>/cancel/",
        api.cancel_reservation_api,
        name="api_cancel_reservation",
    ),
    path("login/", auth.login_page, name="login"),
    path("register/", auth.register_page, name="register"),
    path("logout/", auth.logout_page, name="logout"),
    path("my-reservations/", pages.my_reservations, name="my_reservations"),
    path("owner/", pages.owner_dashboard, name="owner_dashboard"),
]
