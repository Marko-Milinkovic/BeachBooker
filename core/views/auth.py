from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core.models import User, UserRole


def _safe_next_url(request, default_name="explore"):
    candidate = request.GET.get("next") or request.POST.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse(default_name)


def _post_auth_redirect(request, user):
    """Honor ?next= when present; otherwise owners go to the dashboard/setup."""
    candidate = request.GET.get("next") or request.POST.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    if user.role == UserRole.OWNER:
        return reverse("owner_dashboard")
    return reverse("explore")


def login_page(request):
    if request.user.is_authenticated:
        return redirect(_post_auth_redirect(request, request.user))

    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect(_post_auth_redirect(request, user))
        error = "Invalid email or password."

    return render(
        request,
        "core/login.html",
        {
            "error": error,
            "next": request.GET.get("next", ""),
            "email": request.POST.get("email", ""),
        },
    )


def register_page(request):
    if request.user.is_authenticated:
        return redirect(_post_auth_redirect(request, request.user))

    errors = {}
    form_data = {
        "first_name": "",
        "last_name": "",
        "email": "",
        "role": UserRole.REGISTERED,
    }

    if request.method == "POST":
        form_data = {
            "first_name": request.POST.get("first_name", "").strip(),
            "last_name": request.POST.get("last_name", "").strip(),
            "email": request.POST.get("email", "").strip().lower(),
            "role": request.POST.get("role", UserRole.REGISTERED),
        }
        password = request.POST.get("password", "")
        terms = request.POST.get("terms")

        if not form_data["first_name"]:
            errors["first_name"] = "First name is required."
        if not form_data["last_name"]:
            errors["last_name"] = "Last name is required."
        if not form_data["email"]:
            errors["email"] = "Email is required."
        elif User.objects.filter(email=form_data["email"]).exists():
            errors["email"] = "An account with this email already exists."
        if not password:
            errors["password"] = "Password is required."
        if form_data["role"] not in (UserRole.REGISTERED, UserRole.OWNER):
            errors["role"] = "Invalid role."
        if not terms:
            errors["terms"] = "You must accept the terms."

        if not errors:
            user = User.objects.create_user(
                email=form_data["email"],
                password=password,
                first_name=form_data["first_name"],
                last_name=form_data["last_name"],
                role=form_data["role"],
            )
            login(request, user)
            messages.success(request, "Account created. Welcome to BeachBooker!")
            return redirect(_post_auth_redirect(request, user))

    return render(
        request,
        "core/register.html",
        {
            "errors": errors,
            "form": form_data,
            "next": request.GET.get("next", ""),
        },
    )


def logout_page(request):
    logout(request)
    return redirect("index")
