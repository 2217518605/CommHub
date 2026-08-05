from django.urls import path

from .views import AlipayNotifyViewSet, OrderPaymentViewSet, OrderViewSet

urlpatterns = [
    path("order_retrieve/", OrderViewSet.as_view({"get": "list", "post": "create", "put": "update"}), name="order_retrieve"),
    path("order_retrieve/<str:order_number>/", OrderViewSet.as_view({"delete": "destroy"}), name="order_retrieve"),
    path("order_pay/", OrderPaymentViewSet.as_view({"post": "create"}), name="order_pay"),
    path("order_page_pay/", OrderPaymentViewSet.as_view({"post": "page_pay"}), name="order_page_pay"),
    path("order_check_pay/", OrderPaymentViewSet.as_view({"post": "check_pay"}), name="order_check_pay"),
    path("alipay/notify/", AlipayNotifyViewSet.as_view({"post": "post", "get": "get"}), name="alipay_notify"),
    path("balance_pay/", OrderPaymentViewSet.as_view({"post": "balance_pay"}), name="balance_pay"),
]
