from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from core.models import BeachBar
from core.services.beach_bar import get_sunbed_map_payload, parse_filter_date


def bar_sunbeds(request, bar_id):
    bar = get_object_or_404(BeachBar, pk=bar_id)
    filter_date = parse_filter_date(request.GET.get("date"))
    return JsonResponse(get_sunbed_map_payload(bar, filter_date))
