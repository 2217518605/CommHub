import logging
from decimal import Decimal

from django.db import transaction
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.viewsets import ViewSet

from config.authentication import IsCommonUser
from config.decorators.common import api_delete, api_doc, api_post, api_put
from config.help_tools import CommonPageNumberPagination, common_response, get_client_ip, get_object_or_404
from goods_app.models import Goods
from order_app.models import Order, OrderLog
from order_app.serializers import OrderCommonSerializer, OrderQuerySerializer, OrderResponseSerializer
from order_app.validators import create_courier_number, create_order_number, create_transaction_id

logger = logging.getLogger(__name__)


class OrderRetrieveViewSet(ViewSet):
    permission_classes = [IsCommonUser]

    @api_doc(tags=["订单 订单创建"], request_body=OrderCommonSerializer, response_body=OrderResponseSerializer)
    @api_post
    @method_decorator(ratelimit(key="ip", rate="5/m", block=True, method="POST"))  # 防止恶意刷单
    def create(self, request):
        user = request.user
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

        if goods.organization_id != org.id:
            logger.warning("订单 商品不属于当前用户组织，无法创建订单")
            return common_response(status=status.HTTP_400_BAD_REQUEST,
                                   message="订单 商品不属于当前用户组织，无法创建订单")

        if goods.status in [Goods.STATUS_OFFSHELF, Goods.STATUS_SOLDOUT]:
            logger.warning("订单 商品已下架，无法创建订单")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="订单 商品已下架，无法创建订单")

        good_count = serializer.validated_data["good_count"]
        freight_price = serializer.validated_data.get("freight_price") or Decimal("0")
        discount_price = serializer.validated_data.get("discount_price") or Decimal("0")
        total_price = goods.price * good_count
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
                    user_remark=serializer.validated_data.get("user_remark"),
                    admin_remark=serializer.validated_data.get("admin_remark")
                )

                OrderLog.objects.create(order=order, operator=user, operator_name=user.username,
                                        action=OrderLog.ACTION_CREATE_ORDER, message="创建订单成功",
                                        ip_address=get_client_ip(request))

                logger.info(f"订单 创建成功,订单创建人为：{user.username}")
                return common_response(status=status.HTTP_201_CREATED, message="订单 创建成功",
                                       data=OrderResponseSerializer(order).data)
        except Exception as e:
            logger.error(f"订单 创建失败：{e}", exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="订单 创建失败")

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
                    order.status = Order.STATUS_CANCELLED  # 未支付的订单改为已经取消状态
                order.is_deleted = True  # 逻辑上删除
                order.save()

                logger.info(f"订单 删除订单{order_number}成功,订单删除人为：{user.username}")
                return common_response(status=status.HTTP_200_OK, message="订单 删除成功")
        except Exception as e:
            logger.error(f"订单 删除订单失败：{e}", exc_info=True)
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="订单 删除订单失败")


class OrderListView(ViewSet):
    permission_classes = [IsCommonUser]
    pagination_class = CommonPageNumberPagination

    @api_doc(tags=["订单 用户的订单列表"], request_body=OrderQuerySerializer, response_body=OrderResponseSerializer)
    @api_post
    @method_decorator(ratelimit(key="ip", rate="5/m", block=True, method="POST"))
    def list(self, request):
        user = request.user
        user_id = user.id  # 强制要求是登录用户的用户id，不给前端传入
        organization_id = user.organization_id  # 强制要求是登录用户的组织id，不给前端传入
        query_status = request.data.get("query_status")
        query_order_number = request.data.get("query_order_number")

        base_queryset = Order.objects.filter(user_id=user_id, is_deleted=False).select_related("user",
                                                                                               "organization").order_by(
            "-create_time", "-id")

        order_queryset = base_queryset

        if query_order_number:
            order_queryset = order_queryset.filter(order_number__icontains=query_order_number)
        if organization_id:
            order_queryset = order_queryset.filter(organization_id=organization_id)
        if query_status not in [None, ""]:
            order_queryset = order_queryset.filter(status=query_status)

        paginator = self.pagination_class()
        pagination_data = paginator.paginate_queryset(order_queryset, request)
        if pagination_data is None:
            pagination_data = []

        serializer = OrderResponseSerializer(pagination_data, many=True)

        logger.info(f'订单 用户订单查询成功,用户为：{user.username}')
        return paginator.get_paginated_response({
            "status": status.HTTP_200_OK,
            "message": "订单 用户订单查询成功",
            "data": serializer.data
        })
