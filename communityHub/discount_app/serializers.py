import logging

from rest_framework import serializers
from django.utils import timezone

from discount_app.models import CouponTemplate

logger = logging.getLogger(__name__)


class CouponTemplateSerializer(serializers.ModelSerializer):
    """ 优惠卷模板序列化器 """

    valid_from = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S",
                                           input_formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "iso-8601"])
    valid_to = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S",
                                         input_formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "iso-8601"])

    class Meta:
        model = CouponTemplate
        # 创建/更新时可写，但响应不返回
        extra_kwargs = {
            "is_active": {"write_only": True},
            "valid_from": {"write_only": True},
            "valid_to": {"write_only": True}
        }

    def validate_valid_from(self, value):
        if value < timezone.now():
            logger.error("优惠券生效时间不能早于当前时间")
            raise serializers.ValidationError("优惠卷的开始生效时间不能早于当前时间")
        return value

    def validate_valid_to(self, value):
        if value < timezone.now():
            logger.error("优惠券过期时间不能早于当前时间")
            raise serializers.ValidationError("优惠卷的结束时间不能早于当前时间")
        return value

    def validate(self, data):
        if data.get("valid_from") and data.get("valid_to") and data.get("valid_from") > data.get("valid_to"):
            logger.error("优惠券的开始时间不能晚于结束时间")
            raise serializers.ValidationError("优惠券的开始时间不能晚于结束时间")

        if data.get("total_count") and data.get("person_limit_count") and data.get("total_count") < data.get(
                "person_limit_count"):
            logger.error("优惠券总量不能小于每人领取数量")
            raise serializers.ValidationError("优惠券总量不能小于每人领取数量")

        if data.get("type") and isinstance(data.get("type"), int):
            type = int(data.get("type"))
        return data


class CouponTemplateUpdateSerializer(serializers.ModelSerializer):
    # 时间允许调整（如延长活动）
    valid_from = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S",
        input_formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"],
        required=False
    )
    valid_to = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S",
        input_formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"],
        required=False
    )

    class Meta:
        model = CouponTemplate
        fields = ['name', 'description', 'valid_from', 'valid_to',
                  'total_count', 'person_limit_count', 'scope_desc']


class CouponTemplateResponseSerializer(serializers.ModelSerializer):
    """ 优惠卷模板返参序列化器 """

    class Meta:
        model = CouponTemplate
        fields = "__all__"
