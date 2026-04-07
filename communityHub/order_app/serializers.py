import logging
from decimal import Decimal

from rest_framework import serializers

from order_app.models import Order
from user_app.models import User
from organization_app.models import Organization
from goods_app.models import Goods

logger = logging.getLogger(__name__)


class OrderCommonSerializer(serializers.ModelSerializer):
    """ 订单通用入参序列化器(创建、更新) """

    user_id = serializers.IntegerField(help_text="用户ID", required=False)
    organization_id = serializers.IntegerField(help_text="组织ID", required=False)
    goods_id = serializers.IntegerField(help_text="商品ID", required=False, allow_null=True)
    user_coupon_id = serializers.IntegerField(help_text="用户使用的优惠券id", required=False, allow_null=True)

    class Meta:
        model = Order
        exclude = ("user", "organization", "goods")
        extra_kwargs = {
            "goods_name": {"required": False},
            "order_number": {"required": False},
        }
        read_only_fields = ("id", "create_time", "update_time", "pay_price")

    def validate(self, data):
        is_create = self.instance is None
        current_user = self.context.get("user")
        current_organization = self.context.get("organization")
        if is_create:
            if not current_user and not data.get("user_id"):
                raise serializers.ValidationError("用户ID不能为空")
            if not current_organization and not data.get("organization_id"):
                raise serializers.ValidationError("组织ID不能为空")

        good_count = data.get("good_count", self.instance.good_count if self.instance else None)
        if good_count is not None and good_count <= 0:
            logger.error("订单 商品数量必须大于0")
            raise serializers.ValidationError("商品数量必须大于0")

        price_field_labels = {
            "good_price": "商品单件价格",
            "total_price": "订单总价",
            "discount_price": "优惠价格",
            "freight_price": "运费",
            "pay_price": "实际支付价格"
        }
        for field_name, label in price_field_labels.items():
            value = data.get(field_name, getattr(self.instance, field_name, None) if self.instance else None)
            if value is not None and value < 0:
                logger.error(f"订单 {label}不能小于0")
                raise serializers.ValidationError(f"{label}不能小于0")
        return data

    def _get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error("订单 用户不存在")
            raise serializers.ValidationError("用户不存在")

    def _get_organization(self, organization_id):
        try:
            return Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            logger.error("订单 组织不存在")
            raise serializers.ValidationError("组织不存在")

    def _get_goods(self, goods_id):
        try:
            return Goods.objects.get(id=goods_id)
        except Goods.DoesNotExist:
            logger.error("订单 商品不存在")
            raise serializers.ValidationError("商品不存在")

    def _fill_goods_snapshot(self, data, goods):
        """ 填充订单的商品信息快照  """

        if goods and not data.get("goods_name"):
            data["goods_name"] = goods.name
        if goods and not data.get("goods_image"):
            data["goods_image"] = str(goods.small_img or goods.big_img or "")
        if goods and data.get("good_price") is None:
            data["good_price"] = goods.price

    def _calc_price(self, data, base_instance=None):
        """ 计算订单价格 """

        good_price = data.get("good_price", getattr(base_instance, "good_price", None))
        good_count = data.get("good_count", getattr(base_instance, "good_count", None))
        if good_price is not None and good_count is not None and "total_price" not in data:
            data["total_price"] = good_price * good_count

        if "total_price" in data and "pay_price" not in data:
            discount_price = data.get("discount_price", getattr(base_instance, "discount_price", None))
            freight_price = data.get("freight_price", getattr(base_instance, "freight_price", None))
            discount_price = discount_price if discount_price is not None else Decimal("0")
            freight_price = freight_price if freight_price is not None else Decimal("0")
            data["pay_price"] = data["total_price"] - discount_price + freight_price
        return data

    def create(self, validated_data):
        """ 创建订单 """

        user_id = validated_data.pop("user_id", None)
        organization_id = validated_data.pop("organization_id", None)
        goods_id = validated_data.pop("goods_id", None)

        user = self._get_user(user_id)
        organization = self._get_organization(organization_id)
        goods = self._get_goods(goods_id) if goods_id else None

        validated_data["user"] = user
        validated_data["organization"] = organization
        if goods:
            validated_data["goods"] = goods
            self._fill_goods_snapshot(validated_data, goods)

        self._calc_price(validated_data)
        return Order.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """ 更新订单 """

        user_id = validated_data.pop("user_id", serializers.empty)
        organization_id = validated_data.pop("organization_id", serializers.empty)
        goods_id = validated_data.pop("goods_id", serializers.empty)

        if user_id is not serializers.empty:
            instance.user = self._get_user(user_id)
        if organization_id is not serializers.empty:
            instance.organization = self._get_organization(organization_id)
        if goods_id is not serializers.empty:
            if goods_id is None:
                instance.goods = None
            else:
                goods = self._get_goods(goods_id)
                instance.goods = goods
                self._fill_goods_snapshot(validated_data, goods)

        self._calc_price(validated_data, base_instance=instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class OrderResponseSerializer(serializers.ModelSerializer):
    """ 订单返参序列化器 """

    user_name = serializers.CharField(source="user.username", read_only=True, help_text="用户名称")
    organization_name = serializers.CharField(source="organization.org_name", read_only=True, help_text="组织名称")

    class Meta:
        model = Order
        fields = "__all__"


class OrderGetDeleteSerializer(serializers.ModelSerializer):
    """ 获取单个订单或者删除单个订单的通用序列化器 """

    class Meta:
        model = Order
        fields = ["id"]


class OrderQuerySerializer(serializers.ModelSerializer):
    """ 订单查询序列化器 """

    query_order_number = serializers.CharField(help_text="订单编号关键字", allow_blank=True, allow_null=True,
                                               required=False)
    user_id = serializers.IntegerField(help_text="用户ID", required=False, allow_null=True)
    organization_id = serializers.IntegerField(help_text="组织ID", required=False, allow_null=True)
    query_status = serializers.IntegerField(help_text="订单状态", required=False, allow_null=True)

    class Meta:
        model = Order
        fields = ["query_order_number", "user_id", "organization_id", "query_status"]


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    """ 订单状态更新序列化器 """

    id = serializers.IntegerField(help_text="订单ID", required=True)
    status = serializers.IntegerField(help_text="订单状态", required=True)
    admin_remark = serializers.CharField(help_text="后台备注", required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Order
        fields = ["id", "status", "admin_remark"]
