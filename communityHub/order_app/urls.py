from django.urls import path

from .views import OrderListView, OrderRetrieveViewSet

urlpatterns = [
    path("order_retrieve/", OrderRetrieveViewSet.as_view({"post": "create", "put": "update"}), name="order_retrieve"),
    path("order_retrieve/<str:order_number>/", OrderRetrieveViewSet.as_view({"delete": "destroy"}), name="order_retrieve"),
    path("order_list/", OrderListView.as_view({"post": "list"}), name="order_list"),
]
