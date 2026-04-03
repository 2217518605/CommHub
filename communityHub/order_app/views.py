import logging

from rest_framework.viewsets import ViewSet
from rest_framework import status
from rest_framework.decorators import permission_classes
from django_ratelimit.decorators import ratelimit
from django.db import transaction

from config.help_tools import get_object_or_404
from order_app.models import Order, OrderLog
from user_app.models import User
from organization_app.models import Organization
from goods_app.models import Goods
from config.decorators.common import api_doc, api_get, api_post, api_put, api_delete
from order_app.serializers import OrderCommonSerializer, OrderResponseSerializer, OrderQuerySerializer
from config.help_tools import common_response, get_client_ip
from order_app.validators import create_order_number, create_transaction_id, create_courier_number
from config.help_tools import CommonPageNumberPagination

logger = logging.getLogger(__name__)


class OrderRetrieveViewSet(ViewSet):

    @api_doc(tags=["订单 订单创建"], request_body=OrderCommonSerializer, response_body=OrderResponseSerializer)
    @api_post
    @ratelimit(key="ip", rate="5/m", block=True, method="POST")  # 防止恶意刷单
    def create(self, request):

        user = request.user
        org = user.organization
        if not user:
            logger.warning("订单 不存在用户登录信息，无法创建订单")
            return common_response(code=400, msg="订单 不存在用户登录信息，无法创建订单")

        # 校验商品
        goods = get_object_or_404(Goods.objects.select_related("user", "organization"), msg="商品不存在",
                                  id=request.data.get("goods_id"))
        if goods.organization != org:
            logger.warning("订单 商品不属于当前用户组织，无法创建订单")
            return common_response(code=400, msg="订单 商品不属于当前用户组织，无法创建订单")
        if goods.status != Goods.STATUS_CHOICES.normal:
            logger.warning("订单 商品已下架，无法创建订单")
            return common_response(code=400, msg="订单 商品已下架，无法创建订单")

        serializer = OrderCommonSerializer(data=request.data)
        if serializer.is_valid():

            freight_price = request.data.get("freight_price", 0)
            if isinstance(freight_price, str):
                freight_price = float(freight_price)

            good_count = int(request.data.get("good_count"))

            try:
                with transaction.atomic():
                    order = Order.objects.create(
                        user=user,
                        organization=org,
                        goods=goods,
                        order_number=create_order_number(),
                        transaction_id=create_transaction_id(),
                        status=request.data.get("status"),
                        pay_method=request.data.get("pay_method"),
                        pay_time=None,  # 后续付款再改
                        good_price=goods.price,
                        good_count=good_count,
                        total_price=goods.price * good_count,
                        discount_price=None,  # 优惠价格后续开发优惠卷模块再改
                        freight_price=freight_price,
                        pay_price=goods.price * good_count + freight_price,
                        order_remaining_time=None,
                        courier_person=request.data.get("courier_person"),
                        courier_phone=request.data.get("courier_phone"),
                        courier_number=create_courier_number(),
                        address=request.data.get("address"),
                        delivery_time=request.data.get("delivery_time"),
                        source=request.data.get("source"),
                        goods_name=goods.name,
                        goods_spec=request.data.get("goods_spec"),
                        goods_image=goods.big_img,
                        user_remark=request.data.get("user_remark"),
                        admin_remark=request.data.get("admin_remark")
                    )

                    # 订单日志
                    OrderLog.objects.create(order=order, operator=user, operator_name=user.username,
                                            action=OrderLog.ACTION_CHOICES.create_order, message="创建订单成功",
                                            ip_address=get_client_ip(request))

                    logger.info(f'订单 创建成功,订单创建人为：{user.username}')
                    return common_response(status=status.HTTP_201_CREATED, data=OrderResponseSerializer(order).data)
            except Exception as e:
                logger.error(f'订单 创建失败：{e}', exc_info=True)
                return common_response(code=500, msg="订单 创建失败")

    @api_doc(tags=["订单 订单修改"], request_body=OrderCommonSerializer, response_body=OrderResponseSerializer)
    @api_put
    @ratelimit(key="ip", rate="5/m", block=True, method="PUT")
    @transaction.atomic
    def update(self, request):

        user = request.user
        order_number = request.data.get("order_number")
        order = get_object_or_404(Order.objects.select_related("user", "organization"), msg="订单不存在",
                                  order_number=order_number)
        if order.user != request.user:
            logger.warning("订单 修改订单不属于当前用户，无法修改")
            return common_response(code=400, msg="订单 修改订单不属于当前用户，无法修改")
        if order.status != Order.ORDER_STATUS_CHOICES.wait_pay:
            logger.warning("订单 订单已支付，无法修改")
            return common_response(code=400, msg="订单 订单已支付，无法修改")

        serializer = OrderCommonSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():

            allowed_fields = ['address', 'courier_person', 'courier_phone', 'delivery_time', 'user_remark',
                              'admin_remark']

            for field in allowed_fields:
                if field in request.data:
                    setattr(order, field, request.data[field])

            order.save()

            OrderLog.objects.create(order=order, operator=request.user, operator_name=request.user.username,
                                    action=OrderLog.ACTION_CHOICES.update_order, message="修改订单成功",
                                    ip_address=get_client_ip(request))

            logger.info(f'订单 修改订单信息成功,订单创建人为：{user.username}')
            return common_response(status=status.HTTP_200_OK, data=OrderResponseSerializer(order).data)

    @api_doc(tags=["订单 订单删除"], response_body=OrderResponseSerializer)
    @api_delete
    @ratelimit(key="ip", rate="5/m", block=True, method="DELETE")
    def destroy(self, request, order_number):

        user = request.user
        order = get_object_or_404(Order.objects.select_related("user", "organization"), msg="订单不存在",
                                  order_number=order_number)

        if order.user != request.user:
            logger.warning("订单 删除订单不属于当前用户，无权删除")
            return common_response(code=400, msg="订单 删除订单不属于当前用户，无权删除")

        try:
            with transaction.atomic():
                # 记录操作日志
                OrderLog.objects.create(order=order, operator=request.user, operator_name=request.user.username,
                                        action=OrderLog.ACTION_CHOICES.delete_order, message="删除订单成功",
                                        ip_address=get_client_ip(request))

                order.update(is_deleted=True)  # 逻辑上进行删除即可

                logger.info(f'订单 删除订单{order_number}成功,订单删除人为：{user.username}')
                return common_response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f'订单 删除订单失败：{e}', exc_info=True)
            return common_response(code=500, msg="订单 删除订单失败")


class OrderListView(ViewSet):

    @api_doc(tags=["订单 用户的订单列表"], request_body=OrderQuerySerializer, response_body=OrderResponseSerializer)
    @api_post
    @ratelimit(key="ip", rate="5/m", block=True, method="POST")
    def list(self, request):
        pagination = CommonPageNumberPagination()

        user = request.user
        query_order_number = request.data.get("query_order_number")
        user_id = request.data.get("user_id")
        query_status = request.data.get("status")
        if user.id != user_id:
            logger.warning("订单 获取用户订单列表失败，无权限")
            return common_response(code=400, msg="订单 获取用户订单列表失败，无权限")

        base_queryset = Order.objects.filter(user_id=user_id, is_deleted=False).select_related("user",
                                                                                               "organization").order_by(
            "-created_time")

        order_queryset = base_queryset  # 方便链式调用

        if query_order_number:
            order_queryset = order_queryset.filter(order_number__icontains=query_order_number)
        if query_status:
            order_queryset = order_queryset.filter(status=query_status)

        paginator = pagination.paginate_queryset(order_queryset, request)
        if paginator is None:
            paginator = []

        serializer = OrderResponseSerializer(paginator, many=True)

        logger.info(f'订单 用户订单查询成功,用户为：{user.username}')
        return paginator.get_paginated_response({
            "status": status.HTTP_200_OK,
            "message": "订单 用户订单查询成功",
            "data": serializer.data
        })
