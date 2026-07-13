from django.conf import settings


def app_js_version(_request):
    # Used for both JS and CSS query-string cache busting.
    return {
        "APP_JS_VERSION": settings.APP_JS_VERSION,
        "APP_ASSET_VERSION": settings.APP_JS_VERSION,
    }
