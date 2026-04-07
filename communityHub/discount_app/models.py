from django.utils import timezone
from django.db import models

from models.base import BaseModel
from user_app.models import User
from organization_app.models import Organization


class CouponTemplate(BaseModel):
    """ 优惠劵基础模版 """

    # 类型选择
    TYPE_CHOICES = (
        (1, '满减券'),  # 如满100减20
        (2, '折扣券'),  # 打8折
        (3, '现金券'),  # 直接减20元（无门槛）
    )

    version = models.SmallIntegerField(default=1, verbose_name="版本号")
    name = models.CharField(max_length=50, verbose_name="优惠券名称")
    description = models.CharField(max_length=100, verbose_name="优惠券描述")
    type = models.SmallIntegerField(choices=TYPE_CHOICES, verbose_name="优惠券类型")

    # 门槛配置
    min_purchase = models.IntegerField(default=0, verbose_name="最低消费金额(分)", help_text="0表示无门槛")
    discount = models.FloatField(default=1, verbose_name="折扣", help_text="8表示八折")
    # 库存配置
    total_count = models.IntegerField(verbose_name="优惠券总量", help_text="0表示不限制数量", default=0)
    person_limit_count = models.IntegerField(verbose_name="每人限领数量", help_text="0表示不限制数量", default=0)

    is_active = models.BooleanField(default=False, verbose_name="是否激活")  # 到期再激活吧
    scope_desc = models.CharField(max_length=255, blank=True, null=True, verbose_name="适用范围说明")

    # 全局有效期（控制什么时候能领，什么时候失效）
    valid_from = models.DateTimeField(verbose_name="优惠劵模版生效时间", null=True, blank=True)
    valid_to = models.DateTimeField(verbose_name="优惠劵模版过期时间", null=True, blank=True)

    class Meta:
        db_table = "t_coupon_template"
        verbose_name = "优惠券模版"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["-create_time"]),
            models.Index(fields=["is_active"])
        ]

    @property
    def is_effective_now(self) -> bool:
        """判断优惠券是否在有效期内"""

        if not self.is_active:
            return False

        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        return True

    @property
    def status_display(self) -> str:
        """优惠券状态显示"""

        if not self.is_active:
            return "未激活"

        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return "未生效"
        if self.valid_to and now > self.valid_to:
            return "已过期"
        return "生效中"

    def __str__(self):
        return self.name


class UserCoupon(BaseModel):
    """ 用户的优惠卷模型 """

    STATUS_CHOICES = (
        (0, '未使用'),
        (1, '已使用'),
        (2, '已过期'),
        (3, '已锁定'),  # 下单时锁定，防止并发支付时重复使用
    )

    user = models.ForeignKey(User, verbose_name="用户", on_delete=models.SET_NULL, related_name="user_coupons",
                             null=True)
    coupon_template = models.ForeignKey(CouponTemplate, verbose_name="优惠券模版", on_delete=models.PROTECT,
                                        related_name="template_coupons")
    organization = models.ForeignKey(Organization, verbose_name="所属机构", on_delete=models.SET_NULL,
                                     related_name="organization_coupons", null=True)
    order = models.ForeignKey("order_app.Order", verbose_name="关联订单", on_delete=models.SET_NULL, related_name="order_coupons",
                              null=True)

    used_time = models.DateTimeField(blank=True, null=True, verbose_name="使用时间")
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0, verbose_name="优惠券状态")

    # 领券时把模板的数据复制过来(快照)
    snapshot_value = models.IntegerField(verbose_name="优惠金额/折扣(快照)", help_text="领券时的数值")
    snapshot_min_purchase = models.IntegerField(verbose_name="最低消费(快照)", default=0)

    # 两个时间可以修改（用户领券时生成，或者手动延期）
    valid_from = models.DateTimeField(verbose_name="生效时间")
    valid_to = models.DateTimeField(verbose_name="过期时间")

    class Meta:
        db_table = "t_user_coupon"
        verbose_name = "用户优惠券"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["user", "-create_time"]),  # 用户优惠券列表
            models.Index(fields=["status", "-create_time"]),  # 优惠券状态查询
            models.Index(fields=["coupon_template", "-create_time"]),  # 优惠券模版查询
            models.Index(fields=["organization", "-create_time"]),  # 机构优惠券查询
            models.Index(fields=["status", "valid_to"])  # 定时任务清除使用
        ]


class CouponReceiveLog(BaseModel):
    """ 用户优惠劵领取日志 """

    # 领取方式
    RECEIVE_TYPE_CHOICES = (
        (1, '主动领取'),  # 用户在页面点击领取
        (2, '系统发放'),  # 注册送礼、后台手动发
        (3, '积分兑换'),  # 积分商城兑换
    )

    user = models.ForeignKey(User, verbose_name="用户", on_delete=models.SET_NULL, related_name="user_receive_logs",
                             null=True)
    template = models.ForeignKey(CouponTemplate, verbose_name="优惠券模版", on_delete=models.PROTECT,
                                 related_name="coupon_template_receive_logs")
    user_coupon = models.ForeignKey(UserCoupon, verbose_name="领取的优惠券", on_delete=models.SET_NULL,
                                    related_name="user_coupon_receive_logs", null=True)
    organization = models.ForeignKey(Organization, verbose_name="所属机构", on_delete=models.SET_NULL,
                                     related_name="organization_receive_logs", null=True)

    receive_type = models.SmallIntegerField(choices=RECEIVE_TYPE_CHOICES, default=1, verbose_name="领取方式")
    status = models.SmallIntegerField(default=1, verbose_name="状态", help_text="1:成功, 0:失败")
    ip = models.GenericIPAddressField(verbose_name="领取IP", null=True, blank=True)  # 防刷

    class Meta:
        db_table = "t_coupon_receive_log"
        verbose_name = "优惠券领取记录"
        indexes = [
            models.Index(fields=['user', '-create_time']),  # 某人某段时间的领取记录
            models.Index(fields=['template', '-create_time']),
        ]
