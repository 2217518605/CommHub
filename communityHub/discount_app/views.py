import logging

from rest_framework.viewsets import ViewSet
from rest_framework import status
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction

from user_app.models import User
from organization_app.models import Organization
from order_app.models import Order
from goods_app.models import Goods
from discount_app.models import CouponTemplate
from config.decorators.common import api_doc, api_post, api_put
from discount_app.serializers import CouponTemplateSerializer, CouponTemplateResponseSerializer, \
    CouponTemplateUpdateSerializer
from config.help_tools import common_response, get_object_or_404
from config.authentication import IsAdminOrSuper

logger = logging.getLogger(__name__)


class CouponRetrieveViewSet(ViewSet):
    permission_classes = [IsAdminOrSuper]  # 必须管理或者超管登录修改

    @api_doc(tags=["优惠券 优惠卷模板创建"], request_body=CouponTemplateSerializer,
             response_body=CouponTemplateResponseSerializer)
    @api_post
    @method_decorator(ratelimit(key='user', rate='5/m', method='POST', block=True))
    def create(self, request):
        serializer = CouponTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        return common_response(
            status.HTTP_201_CREATED, "创建成功", CouponTemplateResponseSerializer(instance).data)

    @api_doc(tags=["优惠券 优惠卷模板修改"], request_body=CouponTemplateUpdateSerializer,
             response_body=CouponTemplateResponseSerializer)
    @api_put
    @transaction.atomic
    @method_decorator(ratelimit(key='user', rate='5/m', method='PUT', block=True))
    def update(self, request, pk):
        # 悲观锁
        coupon_template = get_object_or_404(
            CouponTemplate.objects.select_for_update().prefetch_related("template_coupons"),
            msg="优惠券模板不存在", pk=pk)

        # 检测是否有人已经领取：
        if coupon_template.template_coupons.exists():
            # 已领取状态下，只允许改名称/描述/时间，不能改金额/门槛
            forbidden_fields = ['type', 'min_purchase', 'discount', 'total_count']
            if any(field in request.data for field in forbidden_fields):
                return common_response(
                    status.HTTP_400_BAD_REQUEST, message="该优惠券已有用户领取，不能修改金额/类型/门槛，只能修改名称、描述或有效期"
                )

        # 优惠券过期就不能再修改了
        now = timezone.now()
        if coupon_template.valid_to and coupon_template.valid_to < now:
            return common_response(
                status.HTTP_400_BAD_REQUEST, message="该优惠券已过期，不能修改"
            )

        # 乐观锁
        mutable_data = request.data.copy()
        current_version = getattr(coupon_template, "version", 0)
        mutable_data["version"] = current_version + 1

        serializer = CouponTemplateUpdateSerializer(coupon_template, data=mutable_data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        logger.info(f"优惠券模板修改成功，id:{instance.id}, 操作人:{request.user.id}")
        return common_response(
            status.HTTP_200_OK, "修改成功", CouponTemplateResponseSerializer(instance).data)
