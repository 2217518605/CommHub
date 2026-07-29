import logging
from decimal import Decimal

from rest_framework import serializers

from wallet_app.models import Wallet, RechargeOrder, BalanceLog
from user_app.models import User

logger = logging.getLogger(__name__)


class RechargeCreateSerializer(serializers.Serializer):
    """ 充值创建请求序列化器 """

    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="充值金额（最小0.01元）"
    )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("充值金额必须大于0")
        if value > Decimal("999999.99"):
            raise serializers.ValidationError("单次充值金额不能超过999999.99")
        return value


class RechargeResponseSerializer(serializers.ModelSerializer):
    """ 充值订单响应序列化器 """

    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = RechargeOrder
        fields = [
            'id', 'recharge_number', 'amount', 'status', 'status_text',
            'pay_time', 'create_time', 'update_time'
        ]


class RechargePaymentSerializer(serializers.Serializer):
    """ 充值支付响应序列化器 """

    recharge_number = serializers.CharField()
    pay_url = serializers.CharField()
    out_trade_no = serializers.CharField()
    total_amount = serializers.CharField()


class WalletResponseSerializer(serializers.ModelSerializer):
    """ 钱包响应序列化器 """

    balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'create_time', 'update_time']

    def get_balance(self, obj):
        return obj.user.balance


class BalanceLogSerializer(serializers.ModelSerializer):
    """ 余额变动日志序列化器 """

    source_type_text = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = BalanceLog
        fields = [
            'id', 'change_amount', 'balance_before', 'balance_after',
            'source_type', 'source_type_text', 'source_id', 'remark',
            'create_time'
        ]
