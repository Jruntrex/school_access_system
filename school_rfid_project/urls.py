from django.contrib import admin
from django.urls import include, path
from ninja import NinjaAPI

from school_access.api import access_router, cards_router, reports_router

api = NinjaAPI(title="School Access API")
api.add_router("/access", access_router)
api.add_router("/cards", cards_router)
api.add_router("/reports", reports_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("", include("school_access.urls")),
]
