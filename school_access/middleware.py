from django.utils.cache import add_never_cache_headers


class NoCacheAuthMiddleware:
    """Adds Cache-Control: no-store for authenticated users so the browser
    back button never shows a cached admin/staff page after logout."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            add_never_cache_headers(response)

        return response
