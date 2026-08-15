import logging

from django.db import DatabaseError
from rest_framework.viewsets import ViewSet
from rest_framework import status
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q, Count, Subquery, OuterRef, IntegerField
from django.db.models.functions import Coalesce

from user_app.models import User
from organization_app.models import Organization
from order_app.models import Order
from goods_app.models import Goods
from discount_app.models import CouponTemplate, UserCoupon, CouponReceiveLog
from config.decorators.common import api_doc, api_post, api_put, api_get, api_delete
from discount_app.serializers import CouponTemplateSerializer, CouponTemplateResponseSerializer, \
    CouponTemplateUpdateSerializer, CouponIDSerializer
from config.help_tools import common_response, get_object_or_404, get_client_ip
from config.authentication import IsAdminOrSuper, IsCommonUser

logger = logging.getLogger(__name__)


class CouponRetrieveViewSet(ViewSet):
    permission_classes = [IsCommonUser]  # 所有登录用户可查看，增改删需管理员

    @api_doc(tags=["优惠券 优惠卷模板创建"], request_body=CouponTemplateSerializer,
             response_body=CouponTemplateResponseSerializer)
    @api_post
    @method_decorator(ratelimit(key='user', rate='5/m', method='POST', block=True))
    def create(self, request):
        if not (request.user.is_staff or request.user.user_type in ["admin", "super_admin"]):
            return common_response(status.HTTP_403_FORBIDDEN, message="无权限，仅管理员可创建")
        serializer = CouponTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        return common_response(
            status.HTTP_201_CREATED, "创建成功", CouponTemplateResponseSerializer(instance).data)

    @api_doc(tags=["优惠券 优惠卷模板列表"], response_body=CouponTemplateResponseSerializer)
    @api_get
    def list(self, request):
        """获取优惠券模板列表；claimable=1 时只返回当前用户可领取的模板"""

        queryset = CouponTemplate.objects.filter(is_active=True).order_by('-create_time')

        if request.query_params.get("claimable"):
            now = timezone.now()
            queryset = queryset.filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=now),
                Q(valid_to__isnull=True) | Q(valid_to__gte=now),
            )

            # 排除用户已达到领取上限的模板
            user_coupon_counts = UserCoupon.objects.filter(
                user=request.user,
                coupon_template=OuterRef('pk')
            ).values('coupon_template').annotate(cnt=Count('id')).values('cnt')

            queryset = queryset.annotate(
                my_count=Coalesce(Subquery(user_coupon_counts, output_field=IntegerField()), 0)
            ).exclude(
                Q(person_limit_count__gt=0) & Q(my_count__gte=F('person_limit_count'))
            )

        serializer = CouponTemplateResponseSerializer(queryset, many=True)
        return common_response(status.HTTP_200_OK, message="获取成功",
                               data={"list": serializer.data, "total": queryset.count()})

    @api_doc(tags=["优惠券 优惠卷模板修改"], request_body=CouponTemplateUpdateSerializer,
             response_body=CouponTemplateResponseSerializer)
    @api_put
    @transaction.atomic
    @method_decorator(ratelimit(key='user', rate='5/m', method='PUT', block=True))
    def update(self, request, pk):
        if not (request.user.is_staff or request.user.user_type in ["admin", "super_admin"]):
            return common_response(status.HTTP_403_FORBIDDEN, message="无权限，仅管理员可修改")
        # 悲观锁
        coupon_template = get_object_or_404(
            CouponTemplate.objects.select_for_update(of=('self',)).prefetch_related("template_coupons"),
            msg="优惠券模板不存在", pk=pk)

        # 检测是否有人已经领取：
        if len(coupon_template.template_coupons.all()) > 0:
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

    @api_doc(tags=["优惠券 优惠券模板删除"], request_body=CouponIDSerializer, response_body=None)
    @transaction.atomic
    @api_delete
    def destroy(self, request, pk):

        user = request.user
        if not (user.is_staff or user.user_type in ["admin", "super_admin"]):
            return common_response(status.HTTP_403_FORBIDDEN, message="无权限，仅管理员可删除")

        try:
            coupon_template = get_object_or_404(
                CouponTemplate.objects.select_for_update(of=('self',)),
                msg="要删除的模板不存在", pk=pk)

            # 查验优惠券是否已经被用户领取：
            claimed = UserCoupon.objects.filter(coupon_template=coupon_template)
            update_rows = claimed.update(status=2)  # 把用户已经领取的标记成过期
            if update_rows == 0:
                coupon_template.delete()
                msg = "优惠券模板已彻底删除"
            else:
                coupon_template.is_active = False
                coupon_template.save()
                msg = "存在用户已领取优惠券，模板已停用，所有已领券标记为过期"
            logger.info(f"优惠券模板删除，优惠券模板id:{pk}, 操作人:{user.id}, 结果:{msg}")
            return common_response(status.HTTP_200_OK, message=msg)
        except DatabaseError as e:
            logger.error(f"删除模板数据库异常 pk:{pk}, err:{str(e)}")
            return common_response(status.HTTP_500_INTERNAL_SERVER_ERROR, message="删除模板数据库异常")
        except Exception as e:
            logger.error(f"删除模板未知异常 pk:{pk}, err:{str(e)}", exc_info=True)
            return common_response(status.HTTP_500_INTERNAL_SERVER_ERROR, message="服务器异常，请联系管理员")


class UserCouponViewSet(ViewSet):
    permission_classes = [IsCommonUser]

    @api_doc(tags=["优惠券 用户领取优惠券"], request_body=CouponIDSerializer,
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
                    
            # 判断优惠券的类型：
            if coupon_template.type == 2:
                # 折扣券
                snapshot_value = coupon_template.discount
            else:
                # 满减券和无门槛券
                snapshot_value = coupon_template.discount_amount

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
                snapshot_value=snapshot_value,
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

    @api_doc(tags=["优惠券 用户优惠券列表"], response_body=None)
    @api_get
    def list(self, request):
        """ 获取当前用户优惠券（默认只返回可用，传 show_all=1 返回全部，传 group_by_template=1 按模板聚合）"""

        now = timezone.now()
        coupons = UserCoupon.objects.select_related("coupon_template").filter(
            user=request.user,
        )
        if not request.query_params.get("show_all"):
            coupons = coupons.filter(
                status=0,
                valid_from__lte=now,
                valid_to__gte=now,
            )
        coupons = coupons.order_by("coupon_template_id", "-create_time")

        if request.query_params.get("group_by_template"):
            # 当前用户可用券（未使用 + 未过期），按模板分组计数
            
            grouped = (UserCoupon.objects.filter(user=request.user,status=0,valid_from__lte=now,valid_to__gte=now)
                       .values("coupon_template_id","valid_from","valid_to",coupon_name=F("coupon_template__name"),
                               coupon_type=F("coupon_template__type"),discount_value=F("snapshot_value"),min_purchase=F("snapshot_min_purchase"))
                .annotate(usable_count=Count("id"))
                .order_by("-usable_count"))

            data = []
            for g in grouped:
                data.append({
                    "coupon_template_id": g["coupon_template_id"],
                    "name": g["coupon_name"],
                    "type": g["coupon_type"],
                    "discount_value": g["discount_value"],
                    "min_purchase": g["min_purchase"],
                    "valid_from": g["valid_from"].strftime("%Y-%m-%d %H:%M:%S") if g["valid_from"] else None,
                    "valid_to": g["valid_to"].strftime("%Y-%m-%d %H:%M:%S") if g["valid_to"] else None,
                    "usable_count": g["usable_count"],
                    "status": 0,
                })
            return common_response(status.HTTP_200_OK, message="获取成功",
                                   data={"list": data, "total": len(data)})

        data = []
        for c in coupons:
            data.append({
                "id": c.id,
                "coupon_template_id": c.coupon_template_id,
                "name": c.coupon_template.name,
                "type": c.coupon_template.type,
                "discount_value": c.snapshot_value,
                "min_purchase": c.snapshot_min_purchase,
                "valid_from": c.valid_from.strftime("%Y-%m-%d %H:%M:%S") if c.valid_from else None,
                "valid_to": c.valid_to.strftime("%Y-%m-%d %H:%M:%S") if c.valid_to else None,
                "status": c.status,
                "used_time": c.used_time.strftime("%Y-%m-%d %H:%M:%S") if c.used_time else None,
            })
        return common_response(status.HTTP_200_OK, message="获取成功",
                               data={"list": data, "total": len(data)})
