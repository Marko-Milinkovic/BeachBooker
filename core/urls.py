from django.urls import path

from core.views import api, auth, owner, pages

urlpatterns = [
    path("", pages.index, name="index"),
    path("explore/", pages.explore, name="explore"),
    path("bars/<int:bar_id>/", pages.beach_bar, name="beach_bar"),
    path("api/explore/bars/", api.explore_bars, name="api_explore_bars"),
    path("api/bars/<int:bar_id>/sunbeds/", api.bar_sunbeds, name="api_bar_sunbeds"),
    path("api/bars/<int:bar_id>/book/", api.book_sunbeds_api, name="api_book_sunbeds"),
    path(
        "api/reservations/<int:reservation_id>/cancel/",
        api.cancel_reservation_api,
        name="api_cancel_reservation",
    ),
    path("api/owner/pricing/", api.owner_update_pricing, name="api_owner_pricing"),
    path("api/owner/bundles/", api.owner_create_bundle, name="api_owner_create_bundle"),
    path(
        "api/owner/bundles/<int:bundle_id>/",
        api.owner_update_bundle,
        name="api_owner_update_bundle",
    ),
    path(
        "api/owner/bundles/<int:bundle_id>/toggle/",
        api.owner_toggle_bundle,
        name="api_owner_toggle_bundle",
    ),
    path("api/owner/layout/", api.owner_layout, name="api_owner_layout"),
    path("login/", auth.login_page, name="login"),
    path("register/", auth.register_page, name="register"),
    path("logout/", auth.logout_page, name="logout"),
    path("my-reservations/", pages.my_reservations, name="my_reservations"),
    path("owner/", owner.dashboard, name="owner_dashboard"),
]
