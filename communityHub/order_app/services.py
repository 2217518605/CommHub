import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from discount_app.models import UserCoupon
from goods_app.models import Goods
from order_app.models import Order, OrderLog

logger = logging.getLogger(__name__)


def release_unpaid_order(order_id, operator=None, operator_name=None, action=None, message=None, ip_address=None):
    """ 给仍未付款的订单释放一次库存和优惠券 """
    
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("user").get(pk=order_id)
        if order.status != Order.STATUS_WAIT_PAY or order.is_deleted:
            return False

        Goods.objects.select_for_update().get(pk=order.goods_id)
        Goods.objects.filter(pk=order.goods_id).update(
            number=F("number") + order.good_count,
            sold_count=F("sold_count") - order.good_count,
        )

        if order.user_coupon_id:
            coupon = UserCoupon.objects.select_for_update().get(pk=order.user_coupon_id)
            coupon.status = 0
            coupon.used_time = None
            coupon.order = None
            coupon.save(update_fields=["status", "used_time", "order", "update_time"])

        order.status = Order.STATUS_CANCELLED
        order.is_deleted = True
        order.save(update_fields=["status", "is_deleted", "update_time"])

        OrderLog.objects.create(
            order=order,
            operator=operator or order.user,
            operator_name=operator_name or getattr(operator or order.user, "username", "system"),
            action=action or OrderLog.ACTION_CANCEL_ORDER,
            message=message or "订单取消，已释放库存和优惠券",
            ip_address=ip_address,
        )

    logger.info("订单资源释放成功: %s", order.order_number)
    return True
