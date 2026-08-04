import logging

from celery import shared_task
from django.utils import timezone

from order_app.models import Order, OrderLog
from order_app.services import release_unpaid_order

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def cancel_expire_orders(self):
    """ 取消超过支付截止时间的未付款订单，释放相关资源 """
    
    now = timezone.now()
    order_ids = list(
        Order.objects.filter(
            status=Order.STATUS_WAIT_PAY,
            is_deleted=False,
            order_remaining_time__isnull=False,
            order_remaining_time__lte=now,  # 订单支付截止时间小于等于当前时间,已经超时
        ).values_list("id", flat=True)
    )

    cancelled_count = 0
    for order_id in order_ids:
        try:
            if release_unpaid_order(
                order_id,
                action=OrderLog.ACTION_SYSTEM_TIMEOUT,
                message="订单支付超时，已释放库存和优惠券",
            ):
                cancelled_count += 1
        except Order.DoesNotExist:
            continue
        except Exception as exc:
            logger.error("取消超时订单失败 order_id=%s: %s", order_id, exc, exc_info=True)

    logger.info("定时任务取消支付超时订单 %s 条", cancelled_count)
    return cancelled_count
