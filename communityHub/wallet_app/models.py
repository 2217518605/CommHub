from django.db import models

from models.base import BaseModel
from user_app.models import User


class Wallet(BaseModel):
    """ 用户钱包模型 """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet', verbose_name='关联用户')

    class Meta:
        db_table = 't_wallet'
        verbose_name = '用户钱包'
        verbose_name_plural = verbose_name


class RechargeOrder(BaseModel):
    """ 用户钱包充值订单模型 """

    class Status:
        PENDING = 0  # 待支付
        PAID = 1  # 已支付
        FAILED = 2  # 支付失败
        EXPIRED = 3  # 已过期

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recharge_orders', verbose_name='关联用户')
    recharge_number = models.CharField(max_length=50, unique=True, verbose_name='充值订单号')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='充值金额')
    status = models.IntegerField(
        verbose_name='支付状态',
        choices=[
            (Status.PENDING, '待支付'),
            (Status.PAID, '已支付'),
            (Status.FAILED, '支付失败'),
            (Status.EXPIRED, '已过期'),
        ],
        default=Status.PENDING
    )
    pay_time = models.DateTimeField(verbose_name='支付时间', null=True, blank=True)

    class Meta:
        db_table = 't_recharge_order'
        verbose_name = '充值订单'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['user', '-create_time']),
            models.Index(fields=['status']),
        ]


class BalanceLog(BaseModel):
    """ 余额变动日志 """

    class SourceType:
        RECHARGE = 0  # 充值
        CONSUME = 1  # 消费
        REFUND = 2  # 退款
        ADJUST = 3  # 后台调整

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='balance_logs', verbose_name='关联用户')
    change_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='变动金额')
    balance_before = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='变动前余额')
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='变动后余额')
    source_type = models.IntegerField(
        verbose_name='来源类型',
        choices=[
            (SourceType.RECHARGE, '充值'),
            (SourceType.CONSUME, '消费'),
            (SourceType.REFUND, '退款'),
            (SourceType.ADJUST, '后台调整'),
        ]
    )
    source_id = models.IntegerField(verbose_name='来源ID（订单/充值单等）', null=True, blank=True)
    remark = models.CharField(max_length=200, verbose_name='备注', null=True, blank=True)
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')

    class Meta:
        db_table = 't_balance_log'
        verbose_name = '余额变动日志'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['user', '-create_time']),
            models.Index(fields=['source_type']),
        ]
