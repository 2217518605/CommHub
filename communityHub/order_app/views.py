import logging
import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.db.models import F
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.viewsets import ViewSet

from config.alipay import AlipayClient
from config.authentication import IsCommonUser
from config.decorators.common import api_delete, api_doc, api_post, api_put
from config.help_tools import CommonPageNumberPagination, common_response, get_client_ip, get_object_or_404
from goods_app.models import Goods
from order_app.models import Order, OrderLog
from order_app.serializers import OrderCreateSerializer, OrderCommonSerializer, OrderQuerySerializer, OrderResponseSerializer
from order_app.validators import create_courier_number, create_order_number, create_transaction_id
from order_app.services import release_unpaid_order
from discount_app.models import UserCoupon
from discount_app.utils import calculate_discount
from user_app.models import User
from wallet_app.models import BalanceLog

logger = logging.getLogger(__name__)


class OrderViewSet(ViewSet):
    permission_classes = [IsCommonUser]

    @api_doc(tags=["订单 订单创建"], request_body=OrderCreateSerializer, response_body=OrderResponseSerializer)
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
        
        idempotency_key = request.data.get("idempotency_key") # 这个是幂等键，防止重复创建订单,前端请求会携带
        if idempotency_key:
            existing_order = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
            if existing_order:
                logger.warning("订单 幂等键已存在，无法创建新的订单")
                return common_response(status=status.HTTP_200_OK, message="订单已存在", data=OrderResponseSerializer(existing_order).data)

        serializer = OrderCreateSerializer(data=request.data, context={"user": user, "organization": org})
        if not serializer.is_valid():
            logger.warning(f"订单 创建失败，参数校验失败：{serializer.errors}")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 创建失败，参数校验失败",
                                data=serializer.errors)

        try:
            with transaction.atomic():
                # 加行锁，防止超卖
                goods = get_object_or_404(Goods.objects.select_related("user", "organization").select_for_update(), msg="商品不存在",
                                        id=serializer.validated_data.get("goods_id"))

                user_coupon = None
                if user_coupon_id:
                    user_coupon = get_object_or_404(UserCoupon.objects.select_related("coupon_template").select_for_update(),
                                                    msg="用户优惠券不存在",
                                                    id=user_coupon_id)

                    if user_coupon.user_id != user.id:
                        logger.warning("订单 优惠券不属于当前用户，无法使用")
                        raise ValidationError("订单 优惠券不属于当前用户，无法使用")
                    
                    if user_coupon.status != 0:
                        logger.warning("订单 优惠券已被使用或已过期")
                        raise ValidationError("订单 优惠券已被使用或已过期")

                    now = timezone.now()
                    if user_coupon.valid_from and user_coupon.valid_from > now:
                        raise ValidationError("订单 优惠券尚未生效")
                    
                    if user_coupon.valid_to and user_coupon.valid_to < now:
                        raise ValidationError("订单 优惠券已过期")

                if goods.organization_id != org.id:
                    logger.warning("订单 商品不属于当前用户组织，无法创建订单")
                    raise ValidationError("订单 商品不属于当前用户组织，无法创建订单")

                if goods.status in [Goods.STATUS_OFFSHELF, Goods.STATUS_SOLDOUT,Goods.STATUS_PENDING]:
                    logger.warning("订单 商品状态异常   ，无法创建订单")
                    raise ValidationError("订单 商品状态异常，无法创建订单")

                good_count = serializer.validated_data["good_count"]
                if goods.number < good_count:
                    logger.warning("订单 商品库存不足，无法创建订单")
                    raise ValidationError("订单 商品库存不足，无法创建订单")
                
                freight_price = serializer.validated_data.get("freight_price") or Decimal("0")
                total_price = goods.price * good_count
                
                if user_coupon:
                    discount_price = calculate_discount(user_coupon,total_price)
                else:
                    discount_price = Decimal("0")
                real_total_price = total_price - discount_price

                pay_price = real_total_price + freight_price
                
                order = Order.objects.create(
                    user=user,
                    organization=org,
                    goods=goods,
                    order_number=create_order_number(),
                    status=serializer.validated_data.get("status", Order.STATUS_WAIT_PAY),
                    pay_method=serializer.validated_data.get("pay_method"),
                    pay_time=serializer.validated_data.get("pay_time"),
                    good_price=goods.price,
                    good_count=good_count,
                    total_price=total_price,
                    discount_price=discount_price,
                    freight_price=freight_price,
                    pay_price=pay_price,
                    order_remaining_time=timezone.now() + timedelta(
                        seconds=settings.ORDER_PAYMENT_TIMEOUT
                    ),
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
                    admin_remark=serializer.validated_data.get("admin_remark"),
                    idempotency_key=idempotency_key
                )

                if user_coupon:
                    user_coupon.status = 3  # 变为锁定状态
                    user_coupon.used_time = timezone.now()
                    user_coupon.order = order
                    user_coupon.save(update_fields=["status", "used_time", "order", "update_time"])

                OrderLog.objects.create(order=order, operator=user, operator_name=user.username,
                                        action=OrderLog.ACTION_CREATE_ORDER, message="创建订单成功",
                                        ip_address=get_client_ip(request))

                # 减少商品库存、增加商品销量
                updated_rows = Goods.objects.filter(id=goods.id, number__gte=good_count).update(
                    number=F('number') - good_count,
                    sold_count=F('sold_count') + good_count
                )

                if updated_rows == 0:
                    raise ValidationError("订单 商品库存不足，无法创建订单")

                logger.info(f"订单 创建成功,订单创建人为：{user.username}")
                return common_response(status=status.HTTP_201_CREATED, message="订单 创建成功",
                                    data=OrderResponseSerializer(order).data)
        
        except ValidationError as e:
            logger.warning(f"订单 创建失败(业务校验)：{e}")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message=str(e))
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

    @api_doc(tags=["订单 订单取消"], response_body=OrderResponseSerializer)
    @api_delete
    @method_decorator(ratelimit(key="ip", rate="5/m", block=True, method="DELETE"))
    def destroy(self, request, order_number):
        user = request.user
        order = get_object_or_404(Order.objects.select_related("user"), msg="订单不存在", order_number=order_number)

        if order.user != request.user:
            logger.warning("订单 删除订单不属于当前用户，无权删除")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="订单 删除订单不属于当前用户，无权删除")

        try:
            released = release_unpaid_order(
                order.id,
                operator=request.user,
                operator_name=request.user.username,
                action=OrderLog.ACTION_CANCEL_ORDER,
                message="用户取消未付款订单，已释放库存和优惠券",
                ip_address=get_client_ip(request),
            )
            if not released:
                return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单当前状态不允许取消")

            logger.info(f"订单 删除订单{order_number}成功,订单删除人为：{user.username}")
            return common_response(status=status.HTTP_200_OK, message="订单 删除成功")
        except Exception as e:
            logger.error(f"订单 删除订单失败：{e}", exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="订单 删除失败")


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
            payment = client.build_qr_payment_url(
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

    @api_doc(tags=["订单 生成支付宝网页支付"], request_body=None, response_body=None)
    @api_post
    def page_pay(self, request):
        """ 生成支付宝网页支付 HTML，前端直接在新窗口打开即可支付 """
        
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
            html = client.build_page_payment_html(
                order_number=order.order_number,
                total_amount=order.pay_price,
                subject=order.goods_name,
                body=f"订单支付-{order.order_number}",
            )
        except Exception as exc:
            logger.error("生成支付宝网页支付失败: %s", exc, exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="生成支付宝网页支付失败")

        return HttpResponse(html)

    @api_doc(tags=["订单 查询支付状态"], request_body=None, response_body=None)
    @api_post
    def check_pay(self, request):
        """ 主动查询支付宝支付状态并更新订单 """
        
        order_number = request.data.get("order_number")
        order = get_object_or_404(Order.objects.select_related("user"), msg="订单不存在",
                                  order_number=order_number)

        if order.user_id != request.user.id:
            return common_response(status=status.HTTP_403_FORBIDDEN, message="无权操作该订单")

        if order.status != Order.STATUS_WAIT_PAY:
            return common_response(status=status.HTTP_200_OK, message="订单已处理", data={
                "order_number": order.order_number,
                "status": order.status,
                "is_paid": order.status != Order.STATUS_WAIT_PAY,
            })

        client = AlipayClient()
        try:
            result = client.query_payment(order.order_number)
        except Exception as exc:
            logger.error("查询支付状态失败: %s", exc, exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="查询支付状态失败")

        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), msg="订单不存在", order_number=order_number)
            # 确认订单是否存在且未支付:
            if order.status != Order.STATUS_WAIT_PAY:
                return common_response(status=status.HTTP_200_OK, message="订单已处理", data={
                    "order_number": order.order_number,
                    "status": order.status,
                    "is_paid": order.status != Order.STATUS_WAIT_PAY,
                })
                
            # 查询支付状态:
            trade_status = result.get("trade_status", "")
            if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
                trade_no = result.get("trade_no", "")
                order.status = Order.STATUS_WAIT_DELIVER
                order.pay_method = Order.PAY_METHOD_ALIPAY
                order.pay_time = order.pay_time or timezone.now()
                order.transaction_id = trade_no or order.transaction_id
                order.save(update_fields=["status", "pay_method", "pay_time", "transaction_id", "update_time"])

                OrderLog.objects.create(
                    order=order, operator=request.user, operator_name=request.user.username,
                    action=OrderLog.ACTION_PAY_SUCCESS,
                    message=f"支付宝支付成功，流水号：{trade_no}",
                    ip_address=get_client_ip(request),
                )
                logger.info(f"订单支付状态同步成功: {order_number}")
                
                # 更新优惠券状态为已使用:
                if order.user_coupon:
                    order.user_coupon.status = 1
                    order.user_coupon.save(update_fields=["status", "update_time"])
                
                return common_response(status=status.HTTP_200_OK, message="支付成功", data={
                    "order_number": order.order_number,
                    "status": order.status,
                    "is_paid": True,
                })

            logger.info(f"订单未支付: {order_number}, trade_status={trade_status}")
            
            # 恢复优惠券状态为未使用:
            if order.user_coupon:
                order.user_coupon.status = 0
                order.user_coupon.save(update_fields=["status", "update_time"])
            
            return common_response(status=status.HTTP_200_OK, message="订单尚未支付", data={
                "order_number": order.order_number,
                "status": order.status,
                "is_paid": False,
            })
            
    @api_doc(tags=["订单 用户钱包支付"], request_body=None, response_body=None)
    @api_post
    @method_decorator(ratelimit(key="ip", rate="5/m", block=True, method="POST"))
    @transaction.atomic
    def balance_pay(self, request):
        """ 用户钱包支付 """
        
        order_number = request.data.get("order_number")
        order = get_object_or_404(Order.objects.select_related("user", "organization", "goods"), msg="订单不存在",order_number=order_number)
        
        # 校验订单:
        if order.user_id != request.user.id:
            logger.warning("订单 用户钱包支付订单不属于当前用户，无权支付")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="订单 用户钱包支付订单不属于当前用户，无权支付")
        if order.status != Order.STATUS_WAIT_PAY:
            logger.warning("订单 用户钱包支付订单状态不正确，无法支付")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 用户钱包支付订单状态不正确，无法支付")
        if order.pay_method != Order.PAY_METHOD_BALANCE:
            logger.warning("订单 用户钱包支付订单支付方式不正确，无法支付")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 用户钱包支付订单支付方式不正确，无法支付")
        
        user = User.objects.select_for_update().get(id=order.user_id)
        if user.balance < order.pay_price:
            logger.warning("订单 用户钱包支付订单余额不足，无法支付")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 用户钱包支付订单余额不足，无法支付")
        
        # 余额变动：
        user_balance_before = user.balance
        user.balance = F('balance') - order.pay_price
        user.save(update_fields=["balance", "update_time"])
        user.refresh_from_db() # 刷新用户余额，避免缓存问题
        user_balance_after = user.balance
        BalanceLog.objects.create(
            user=user,
            change_amount=-order.pay_price,
            balance_before=user_balance_before,
            balance_after=user_balance_after,
            source_type=BalanceLog.SourceType.CONSUME,
            source_id = order.id,
            remark=f"订单支付-{order.order_number}，使用用户钱包支付，支付金额：{order.pay_price}"
        )
        
        # 更新优惠券：
        if order.user_coupon:
            order.user_coupon.status = 1
            order.user_coupon.save(update_fields=["status", "update_time"])
            
        # 更新订单：
        order.status = Order.STATUS_WAIT_DELIVER
        order.pay_method = Order.PAY_METHOD_BALANCE
        order.pay_time = order.pay_time or timezone.now()
        order.save(update_fields=["status", "pay_method", "pay_time", "update_time"])
        
        # 创建订单日志：
        OrderLog.objects.create(
            order=order, operator=request.user, operator_name=request.user.username,
            action=OrderLog.ACTION_PAY_SUCCESS,
            message=f"用户钱包支付成功，支付金额：{order.pay_price}",
            ip_address=get_client_ip(request)
        )
        
        logger.info(f"订单 用户钱包支付成功: {order_number}")
        return common_response(status=status.HTTP_200_OK, message="订单 用户钱包支付成功")


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
                
                # 校验订单金额和交易金额是否一致:                
                if Decimal(order.pay_price) != Decimal(total_amount):
                    logger.warning(f"订单金额和交易金额不一致，订单号：{order.order_number}，订单金额：{order.pay_price}，交易金额：{total_amount}")
                    
                    OrderLog.objects.create(
                        order=order,
                        operator=order.user,
                        operator_name=order.user.username,
                        action=OrderLog.ACTION_PAY_FAILED,
                        message=f"支付宝支付失败，订单金额和交易金额不一致，订单号：{order.order_number}，订单金额：{order.pay_price}，交易金额：{total_amount}",
                        ip_address=get_client_ip(request),
                    )
                    return HttpResponse("error")
                
                # 校验 app_id 是否一致:
                app_id = os.getenv("ALIPAY_APP_ID")
                if app_id != payload.get("app_id"):
                    logger.warning(f"支付宝回调订单app_id不一致，订单号：{order.order_number}，订单app_id：{app_id}，回调app_id：{payload.get('app_id')}")
                    
                    OrderLog.objects.create(
                        order=order,
                        operator=order.user,
                        operator_name=order.user.username,
                        action=OrderLog.ACTION_PAY_FAILED,
                        message=f"支付宝支付失败，订单app_id不一致，订单号：{order.order_number}，订单app_id：{app_id}，回调app_id：{payload.get('app_id')}",
                        ip_address=get_client_ip(request),
                    )
                    return HttpResponse("error")
                
                if order.status == Order.STATUS_WAIT_PAY:
                    order.status = Order.STATUS_WAIT_DELIVER
                    order.pay_method = Order.PAY_METHOD_ALIPAY
                    order.pay_time = order.pay_time or timezone.now()
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
                    
                    # 更新优惠券状态:
                    order.user_coupon.status = 1
                    order.user_coupon.save(update_fields=["status", "update_time"])
                    
        except Order.DoesNotExist:
            logger.warning("支付宝回调订单不存在: %s", out_trade_no)
            return HttpResponse("success")

        return HttpResponse("success")

    @api_doc(tags=["订单 支付宝同步跳转"], request_body=None, response_body=None)
    def get(self, request):
        """处理支付宝同步跳转回调。"""
        
        return self.post(request)
