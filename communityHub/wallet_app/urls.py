from django.urls import path

from .views import (
    WalletViewSet, RechargeViewSet, RechargePaymentViewSet, AlipayRechargeNotifyViewSet
)

urlpatterns = [
    # 充值支付（优先匹配更长的路径）
    path("recharge/pay/", RechargePaymentViewSet.as_view({"post": "create"}), name="recharge_pay"),
    path("recharge/pay/page/", RechargePaymentViewSet.as_view({"post": "page_pay"}), name="recharge_page_pay"),
    path("recharge/pay/check/", RechargePaymentViewSet.as_view({"post": "check_pay"}), name="recharge_check_pay"),

    # 充值
    path("recharge/", RechargeViewSet.as_view({"get": "list", "post": "create", "delete": "bulk_destroy"}), name="recharge_create"),
    path("recharge/<str:recharge_number>/", RechargeViewSet.as_view({"get": "retrieve", "delete": "destroy"}), name="recharge_detail"),

    # 支付宝回调
    path("recharge/alipay/notify/", AlipayRechargeNotifyViewSet.as_view({"post": "post", "get": "get"}), name="recharge_alipay_notify"),

    # 钱包相关
    path("wallet/", WalletViewSet.as_view({"get": "get_wallet"}), name="wallet_info"),
    path("wallet/logs/", WalletViewSet.as_view({"get": "list_balance_logs", "delete": "clear_balance_logs"}), name="balance_logs"),
    path("wallet/logs/bulk/", WalletViewSet.as_view({"post": "bulk_destroy_balance_logs"}), name="balance_logs_bulk"),
    path("wallet/logs/<int:log_id>/", WalletViewSet.as_view({"delete": "destroy_balance_log"}), name="balance_log_detail"),
]
