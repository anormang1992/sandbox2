from django.urls import include, path
from rest_framework import routers

from . import views


class BulkPatchRouter(routers.DefaultRouter):
    """
    DefaultRouter that additionally binds ``PATCH`` on each viewset's list
    URL to a ``partial_update_list`` method when one is defined.

    DRF's built-in routers only map ``GET`` and ``POST`` to the list URL.
    Rather than shadowing the router with a second URL pattern (which forces
    a duplicate ``{basename}-list`` name and relies on URL-resolution order),
    this subclass rewrites the list route's method mapping in place.
    """

    def get_routes(self, viewset):
        routes = super().get_routes(viewset)
        if not hasattr(viewset, "partial_update_list"):
            return routes

        updated = []
        for route in routes:
            if route.name == "{basename}-list":
                route = route._replace(
                    mapping={**route.mapping, "patch": "partial_update_list"},
                )
            updated.append(route)
        return updated


router = BulkPatchRouter()
router.register(r"users", views.UserViewSet)
router.register(r"groups", views.GroupViewSet)
router.register(r"questions", views.QuestionViewSet)
router.register(r"choices", views.ChoiceViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
]
