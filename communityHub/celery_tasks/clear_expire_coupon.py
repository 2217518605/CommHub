import logging

from celery import shared_task
from django.utils import timezone
from django.db import transaction

from discount_app.models import CouponTemplate, UserCoupon

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def clear_expire_coupon(self):
    """ 清除用户过期的优惠券和优惠券模板 """

    try:
        now = timezone.now()

        """ 处理用户手中的过期优惠券 """
        with transaction.atomic():
            user_coupon = UserCoupon.objects.filter(status=0, valid_to__lt=now)  # 未使用且过期了
            count = user_coupon.update(status=2)  # 过期
            logger.info("定时任务 清除用户过期优惠券 %s 条" % count)

        """ 处理过期的优惠券模板 """
        coupon_template = CouponTemplate.objects.filter(is_active=True, valid_to__lt=now)
        # 判断优惠券是否被用户领取
        delete_count = 0
        for template in coupon_template.iterator():  # 防止内存溢出
            if not template.template_coupons.exists():
                template.delete()
                delete_count += 1
                logger.info(f"定时任务：删除过期且无人领取的模板 - {template.name} (ID: {template.id})")

        logger.info("定时任务 清除过期优惠券模版 %s 条" % delete_count)

    except Exception as e:
        logger.error(f"定时任务执行失败: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)
