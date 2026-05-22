from django.urls import path, include

urlpatterns = [
    path("", include("parser_api.urls")),
    path("api/", include("parser_api.urls")),
]
