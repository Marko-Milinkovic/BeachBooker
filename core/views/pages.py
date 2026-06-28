from django.shortcuts import render


def index(request):
    """Home page — scaffold placeholder."""
    return render(request, "core/index.html")
