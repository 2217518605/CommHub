import logging
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.viewsets import ViewSet

from config.alipay import AlipayClient
from config.authentication import IsCommonUser
from config.decorators.common import api_delete, api_doc, api_post, api_put
from config.help_tools import CommonPageNumberPagination, common_response, get_client_ip, get_object_or_404
from goods_app.models import Goods
from order_app.models import Order, OrderLog
from order_app.serializers import OrderCommonSerializer, OrderQuerySerializer, OrderResponseSerializer
from order_app.validators import create_courier_number, create_order_number, create_transaction_id
from discount_app.models import UserCoupon

logger = logging.getLogger(__name__)


class OrderRetrieveViewSet(ViewSet):
    permission_classes = [IsCommonUser]

    @api_doc(tags=["订单 订单创建"], request_body=OrderCommonSerializer, response_body=OrderResponseSerializer)
    @api_post
    @method_decorator(ratelimit(key="ip", rate="5/m", block=True, method="POST"))  # 防止恶意刷单
    def create(self, request):
        user = request.user
        user_coupon_id = request.data.get("user_coupon_id")
        if not user:
            logger.warning("订单 不存在用户登录信息，无法创建订单")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 不存在用户登录信息，无法创建订单")

        org = getattr(user, "organization", None)
        if not org:
            logger.warning("订单 当前用户未加入组织，无法创建订单")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="订单 当前用户未加入组织，无法创建订单")

        serializer = OrderCommonSerializer(data=request.data, context={"user": user, "organization": org})
        if not serializer.is_valid():
            logger.warning(f"订单 创建失败，参数校验失败：{serializer.errors}")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 创建失败，参数校验失败",
                                   data=serializer.errors)

        goods = get_object_or_404(Goods.objects.select_related("user", "organization"), msg="商品不存在",
                                  id=serializer.validated_data.get("goods_id"))

        user_coupon = None
        if user_coupon_id:
            user_coupon = get_object_or_404(UserCoupon.objects.select_related("coupon_template"),
                                            msg="用户优惠券不存在",
                                            id=user_coupon_id)

            if user_coupon.user_id != user.id:
                logger.warning("订单 优惠券不属于当前用户，无法使用")
                return common_response(status=status.HTTP_400_BAD_REQUEST,
                                       message="订单 优惠券不属于当前用户，无法使用")
            if user_coupon.status != 0:
                logger.warning("订单 优惠券已被使用或已过期")
                return common_response(status=status.HTTP_400_BAD_REQUEST,
                                       message="订单 优惠券已被使用或已过期")

            now = timezone.now()
            if user_coupon.valid_from and user_coupon.valid_from > now:
                return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 优惠券尚未生效")
            if user_coupon.valid_to and user_coupon.valid_to < now:
                return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 优惠券已过期")

        if goods.organization_id != org.id:
            logger.warning("订单 商品不属于当前用户组织，无法创建订单")
            return common_response(status=status.HTTP_400_BAD_REQUEST,
                                   message="订单 商品不属于当前用户组织，无法创建订单")

        if goods.status in [Goods.STATUS_OFFSHELF, Goods.STATUS_SOLDOUT]:
            logger.warning("订单 商品已下架，无法创建订单")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 商品已下架，无法创建订单")

        good_count = serializer.validated_data["good_count"]
        freight_price = serializer.validated_data.get("freight_price") or Decimal("0")
        discount_price = user_coupon.snapshot_value if user_coupon else Decimal("0")
        total_price = goods.price * good_count

        if user_coupon:
            snapshot_min_purchase = user_coupon.snapshot_min_purchase
            if total_price < snapshot_min_purchase:
                logger.warning("订单 优惠券不满足最低使用金额，无法创建订单")
                return common_response(status=status.HTTP_400_BAD_REQUEST,
                                       message="订单 优惠券不满足最低使用金额，无法创建订单")

        pay_price = total_price - discount_price + freight_price
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    user=user,
                    organization=org,
                    goods=goods,
                    order_number=create_order_number(),
                    transaction_id=create_transaction_id(),
                    status=serializer.validated_data.get("status", Order.STATUS_WAIT_PAY),
                    pay_method=serializer.validated_data.get("pay_method"),
                    pay_time=serializer.validated_data.get("pay_time"),
                    good_price=goods.price,
                    good_count=good_count,
                    total_price=total_price,
                    discount_price=discount_price,
                    freight_price=freight_price,
                    pay_price=pay_price,
                    order_remaining_time=serializer.validated_data.get("order_remaining_time"),
                    courier_person=serializer.validated_data.get("courier_person"),
                    courier_phone=serializer.validated_data.get("courier_phone"),
                    courier_number=create_courier_number(),
                    address=serializer.validated_data.get("address"),
                    delivery_time=serializer.validated_data.get("delivery_time"),
                    source=serializer.validated_data.get("source", Order.SOURCE_WECHAT_MINI_PROGRAM),
                    goods_name=goods.name,
                    goods_spec=serializer.validated_data.get("goods_spec") or {},
                    goods_image=str(goods.big_img or goods.small_img or ""),
                    user_coupon=user_coupon,
                    user_remark=serializer.validated_data.get("user_remark"),
                    admin_remark=serializer.validated_data.get("admin_remark")
                )

                if user_coupon:
                    user_coupon.status = 1
                    user_coupon.used_time = timezone.now()
                    user_coupon.order = order
                    user_coupon.save(update_fields=["status", "used_time", "order", "update_time"])

                OrderLog.objects.create(order=order, operator=user, operator_name=user.username,
                                        action=OrderLog.ACTION_CREATE_ORDER, message="创建订单成功",
                                        ip_address=get_client_ip(request))

                logger.info(f"订单 创建成功,订单创建人为：{user.username}")
                return common_response(status=status.HTTP_201_CREATED, message="订单 创建成功",
                                       data=OrderResponseSerializer(order).data)
        except Exception as e:
            logger.error(f"订单 创建失败：{e}", exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="订单 创建失败")

    @api_doc(tags=["订单 订单列表"], response_body=OrderResponseSerializer)
    def list(self, request):
        """获取当前用户的订单列表（分页）"""

        user = request.user
        if not user:
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 用户未登录")

        queryset = Order.objects.select_related("user", "organization").filter(
            user=user, is_deleted=False
        ).order_by('-create_time')

        paginator = CommonPageNumberPagination()
        paginated_data = paginator.paginate_queryset(queryset, request)
        serializer = OrderResponseSerializer(paginated_data, many=True)

        return paginator.get_paginated_response(serializer.data)

    @api_doc(tags=["订单 订单修改"], request_body=OrderCommonSerializer, response_body=OrderResponseSerializer)
    @api_put
    @method_decorator(ratelimit(key="ip", rate="5/m", block=True, method="PUT"))
    @transaction.atomic
    def update(self, request):
        user = request.user
        order_number = request.data.get("order_number")
        order = get_object_or_404(Order.objects.select_related("user", "organization"), msg="订单不存在",
                                  order_number=order_number)
        if order.user != request.user:
            logger.warning("订单 修改订单不属于当前用户，无法修改")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="订单 修改订单不属于当前用户，无法修改")
        if order.status != Order.STATUS_WAIT_PAY:
            logger.warning("订单 订单已支付，无法修改")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 订单已支付，无法修改")

        serializer = OrderCommonSerializer(order, data=request.data, partial=True,
                                           context={"user": user, "organization": order.organization})
        if not serializer.is_valid():
            logger.warning(f"订单 修改失败，参数校验失败：{serializer.errors}")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 修改失败，参数校验失败",
                                   data=serializer.errors)

        allowed_fields = ["address", "courier_person", "courier_phone", "delivery_time", "user_remark",
                          "admin_remark", "goods_spec"]
        updated_fields = []
        for field in allowed_fields:
            if field in serializer.validated_data:
                setattr(order, field, serializer.validated_data[field])
                updated_fields.append(field)

        order.save()

        action = OrderLog.ACTION_UPDATE_ADDRESS
        if updated_fields and set(updated_fields).issubset({"user_remark", "admin_remark"}):
            action = OrderLog.ACTION_ADMIN_REMARK

        OrderLog.objects.create(order=order, operator=request.user, operator_name=request.user.username,
                                action=action, message="修改订单成功", ip_address=get_client_ip(request))

        logger.info(f"订单 修改订单信息成功,订单创建人为：{user.username}")
        return common_response(status=status.HTTP_200_OK, message="订单 修改成功",
                               data=OrderResponseSerializer(order).data)

    @api_doc(tags=["订单 订单删除"], response_body=OrderResponseSerializer)
    @api_delete
    @method_decorator(ratelimit(key="ip", rate="5/m", block=True, method="DELETE"))
    def destroy(self, request, order_number):
        user = request.user
        order = get_object_or_404(Order.objects.select_related("user", "organization"), msg="订单不存在",
                                  order_number=order_number)

        if order.user != request.user:
            logger.warning("订单 删除订单不属于当前用户，无权删除")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="订单 删除订单不属于当前用户，无权删除")

        try:
            with transaction.atomic():
                OrderLog.objects.create(order=order, operator=request.user, operator_name=request.user.username,
                                        action=OrderLog.ACTION_CANCEL_ORDER, message="删除订单成功",
                                        ip_address=get_client_ip(request))

                if order.status == Order.STATUS_WAIT_PAY:
                    order.status = Order.STATUS_CANCELLED
                order.is_deleted = True
                order.save()

                logger.info(f"订单 删除订单{order_number}成功,订单删除人为：{user.username}")
                return common_response(status=status.HTTP_200_OK, message="订单 删除成功")
        except Exception as e:
            logger.error(f"订单 删除订单失败：{e}", exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="订单 删除订单失败")


class OrderPaymentViewSet(ViewSet):
    permission_classes = [IsCommonUser]

    @api_doc(tags=["订单 生成支付宝支付链接"], request_body=None, response_body=None)
    @api_post
    def create(self, request):
        order_number = request.data.get("order_number")
        order = get_object_or_404(Order.objects.select_related("user", "organization", "goods"), msg="订单不存在",
                                  order_number=order_number)

        if order.user_id != request.user.id:
            return common_response(status=status.HTTP_403_FORBIDDEN, message="无权操作该订单")
        if order.status != Order.STATUS_WAIT_PAY:
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单当前状态不允许支付")
        if order.pay_method != Order.PAY_METHOD_ALIPAY:
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="当前订单不是支付宝支付方式")

        client = AlipayClient()
        try:
            payment = client.build_payment_url(
                order_number=order.order_number,
                total_amount=order.pay_price,
                subject=order.goods_name,
                body=f"订单支付-{order.order_number}",
            )
        except Exception as exc:
            logger.error("生成支付宝支付链接失败: %s", exc, exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="生成支付宝支付链接失败")

        return common_response(status=status.HTTP_200_OK, message="生成支付宝支付链接成功", data={
            "order_number": payment.order_number,
            "pay_url": payment.pay_url,
            "out_trade_no": payment.out_trade_no,
            "total_amount": payment.total_amount,
        })


class AlipayNotifyViewSet(ViewSet):
    authentication_classes = []
    permission_classes = []

    @api_doc(tags=["订单 处理支付宝异步通知回调"], request_body=None, response_body=None)
    def post(self, request):
        client = AlipayClient()
        payload = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
        if not client.verify_notify(payload):
            return HttpResponse("failure", status=400)

        trade_status = payload.get("trade_status")
        out_trade_no = payload.get("out_trade_no")
        trade_no = payload.get("trade_no")
        total_amount = payload.get("total_amount")

        if trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
            return HttpResponse("success")

        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(order_number=out_trade_no)
                if order.status == Order.STATUS_WAIT_PAY:
                    order.status = Order.STATUS_WAIT_DELIVER
                    order.pay_method = Order.PAY_METHOD_ALIPAY
                    order.pay_time = order.pay_time or order.create_time
                    order.transaction_id = trade_no or order.transaction_id
                    order.save(update_fields=["status", "pay_method", "pay_time", "transaction_id", "update_time"])
                    OrderLog.objects.create(
                        order=order,
                        operator=order.user,
                        operator_name=order.user.username,
                        action=OrderLog.ACTION_PAY_SUCCESS,
                        message=f"支付宝支付成功，流水号：{trade_no}，金额：{total_amount}",
                        ip_address=get_client_ip(request),
                    )
        except Order.DoesNotExist:
            logger.warning("支付宝回调订单不存在: %s", out_trade_no)
            return HttpResponse("success")

        return HttpResponse("success")

    @api_doc(tags=["订单 支付宝同步跳转"], request_body=None, response_body=None)
    def get(self, request):
        """处理支付宝同步跳转回调。"""
        return self.post(request)
