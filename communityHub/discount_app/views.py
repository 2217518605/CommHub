import logging

from rest_framework.viewsets import ViewSet
from rest_framework import status
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction
from django.db.models import F

from user_app.models import User
from organization_app.models import Organization
from order_app.models import Order
from goods_app.models import Goods
from discount_app.models import CouponTemplate, UserCoupon, CouponReceiveLog
from config.decorators.common import api_doc, api_post, api_put
from discount_app.serializers import CouponTemplateSerializer, CouponTemplateResponseSerializer, \
    CouponTemplateUpdateSerializer, UserCouponSerializer
from config.help_tools import common_response, get_object_or_404, get_client_ip
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


class UserCouponViewSet(ViewSet):

    @api_doc(tags=["优惠券 用户领取优惠券"], request_body=UserCouponSerializer,
             response_body=CouponTemplateResponseSerializer)
    @transaction.atomic
    @method_decorator(ratelimit(key='user', rate='10/m', method='POST', block=True))
    @method_decorator(ratelimit(key='ip', rate='30/m', method='POST', block=True))
    @api_post
    def create(self, request):

        coupon_template_id = request.data.get("coupon_template_id")
        coupon_template = get_object_or_404(
            CouponTemplate.objects.select_for_update().prefetch_related("template_coupons"),
            msg="优惠券模板不存在", pk=coupon_template_id)

        if coupon_template.is_active == False:
            return common_response(
                status.HTTP_400_BAD_REQUEST, message="该优惠券已失效"
            )

        now = timezone.now()
        if coupon_template.valid_from and coupon_template.valid_from > now:
            return common_response(
                status.HTTP_400_BAD_REQUEST, message="该优惠券未到生效时间"
            )

        if coupon_template.valid_to and coupon_template.valid_to < now:
            return common_response(
                status.HTTP_400_BAD_REQUEST, message="该优惠券已过期"
            )

        try:
            # 检测库存：
            if coupon_template.total_count > 0:
                # 必须再检测一次，因为select_for_update() 锁的是行
                if coupon_template.total_count <= 0:
                    return common_response(
                        status.HTTP_400_BAD_REQUEST, message="该优惠券已经被抢光了，无库存"
                    )
                # 库存减1（高并发下必须再查一次，避免是旧数据）(原子操作)
                count = CouponTemplate.objects.filter(id=coupon_template_id, total_count__gt=0).update(
                    total_count=F("total_count") - 1)
                if count == 0:
                    return common_response(
                        status.HTTP_400_BAD_REQUEST, message="该优惠券已经被抢光了，无库存"
                    )
                # 刷新coupon_template 对象
                coupon_template.refresh_from_db()

            # 检测用户领取数量限制
            if coupon_template.person_limit_count > 0:
                count = UserCoupon.objects.filter(user=request.user,
                                                  coupon_template_id=coupon_template_id).count()
                if count >= coupon_template.person_limit_count:
                    return common_response(
                        status.HTTP_400_BAD_REQUEST,
                        message=f"每个用户限领{coupon_template.person_limit_count}张优惠券"
                    )

            # 发劵：
            user_coupon = UserCoupon.objects.create(
                user=request.user,
                coupon_template=coupon_template,
                organization=request.user.organization,
                valid_from=coupon_template.valid_from,
                valid_to=coupon_template.valid_to,
                order=None,
                used_time=None,
                status=0,
                snapshot_value=coupon_template.discount,
                snapshot_min_purchase=coupon_template.min_purchase
            )

            # 记录领取日志
            CouponReceiveLog.objects.create(
                user=request.user,
                template=coupon_template,
                user_coupon=user_coupon,
                organization=request.user.organization,
                receive_type=request.data.get("receive_type", 1),
                status=1,
                ip=get_client_ip(request)
            )
            logger.info(
                f"用户领取优惠券成功，id:{user_coupon.id}, 优惠券模版id:{coupon_template.id}, 用户id:{request.user.id}")
            return common_response(
                status.HTTP_200_OK, "领取优惠券成功", CouponTemplateResponseSerializer(coupon_template).data)
        except Exception as e:
            logger.error(
                f"用户领取优惠券失败，优惠券模版id:{coupon_template.id}, 用户id:{request.user.id}, 错误信息:{e}")
            return common_response(
                status.HTTP_400_BAD_REQUEST, message="领取优惠券失败")
