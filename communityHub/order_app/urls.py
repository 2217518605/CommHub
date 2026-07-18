from django.urls import path

from .views import AlipayNotifyViewSet, OrderPaymentViewSet, OrderRetrieveViewSet

urlpatterns = [
    path("order_retrieve/", OrderRetrieveViewSet.as_view({"post": "create", "put": "update"}), name="order_retrieve"),
    path("order_retrieve/<str:order_number>/", OrderRetrieveViewSet.as_view({"delete": "destroy"}), name="order_retrieve"),
    path("order_pay/", OrderPaymentViewSet.as_view({"post": "create"}), name="order_pay"),
    path("alipay/notify/", AlipayNotifyViewSet.as_view({"post": "post", "get": "get"}), name="alipay_notify"),
]
