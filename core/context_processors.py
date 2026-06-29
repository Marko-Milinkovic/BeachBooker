from django.conf import settings


def app_js_version(_request):
    return {"APP_JS_VERSION": settings.APP_JS_VERSION}
