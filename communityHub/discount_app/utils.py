import logging

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def calculate_discount(user_coupon,total_price):
    """ 计算折扣金额 """
    
    if user_coupon.coupon_template.type == 1:
        """ 满减券 """
        
        if total_price < user_coupon.snapshot_min_purchase:
            logger.error(f"订单金额小于满减券最低消费金额: {total_price} < {user_coupon.snapshot_min_purchase}")
            raise ValidationError("订单金额小于满减券最低消费金额")
        
        discount_amount = user_coupon.snapshot_value
        return min(discount_amount,total_price)
    
    elif user_coupon.coupon_template.type == 2:
        """ 折扣券 """
        
        if total_price < user_coupon.snapshot_min_purchase:
            logger.error(f"订单金额小于折扣券最低消费金额: {total_price} < {user_coupon.snapshot_min_purchase}")
            raise ValidationError("订单金额小于折扣券最低消费金额")
        
        if user_coupon.snapshot_value < 1 or user_coupon.snapshot_value > 10:
            logger.error(f"折扣券折扣率不合法: {user_coupon.snapshot_value}")
            raise ValidationError("折扣券折扣率不合法")
        
        discount_amount = total_price * (10-user_coupon.snapshot_value) / 10
        return min(discount_amount,total_price)
    
    elif user_coupon.coupon_template.type == 3:
        """ 无门槛券 """
        
        discount_amount = user_coupon.snapshot_value
        return min(discount_amount,total_price)
        
        