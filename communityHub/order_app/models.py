from django.db import models

from models.base import BaseModel
from user_app.models import User
from organization_app.models import Organization
from goods_app.models import Goods


class Order(BaseModel):
    """ 订单模型 """

    ORDER_STATUS_CHOICES = (
        (1, "待付款"),
        (2, "待发货"),
        (3, "待收货"),
        (4, "待评价"),
        (5, "已完成"),
        (6, "已取消"),
    )

    PAY_METHOD_CHOICES = (
        (1, "支付宝"),
        (2, "微信"),
        (3, "货到付款"),
    )

    SOURCE_CHOICES = (
        (1, "微信小程序"), (2, "H5"), (3, "App"), (4, "后台录入"),
    )

    user = models.ForeignKey(User, verbose_name="用户", on_delete=models.CASCADE, related_name="user_order",
                             blank=False, null=False, db_index=True)
    organization = models.ForeignKey(Organization, verbose_name="组织", on_delete=models.CASCADE,
                                     related_name="organization_order", blank=False, null=False)
    goods = models.ForeignKey(Goods, verbose_name="商品", on_delete=models.SET_NULL, related_name="goods_order",
                              null=True, blank=True)
    # coupon = models.ForeignKey("Coupon", verbose_name="优惠券", on_delete=models.CASCADE, related_name="coupon_order",
    #                            blank=True, null=True) # 后续和优惠卷模型关联进行金额操作

    order_number = models.CharField(verbose_name="订单编号", max_length=128, blank=False, null=False, unique=True,
                                    db_index=True)
    # 第三方交易流水号 (用于退款、对账)
    transaction_id = models.CharField(verbose_name="第三方流水号", max_length=64, blank=True, null=True, db_index=True)

    status = models.IntegerField(choices=ORDER_STATUS_CHOICES, verbose_name="订单状态", default=1, blank=False,
                                 null=False)

    pay_time = models.DateTimeField(verbose_name="支付时间", blank=True, null=True)
    pay_method = models.SmallIntegerField(choices=PAY_METHOD_CHOICES, verbose_name="支付方式", blank=True, null=True)

    good_price = models.DecimalField(verbose_name="商品单件价格", max_digits=10, decimal_places=2, default=0)
    good_count = models.IntegerField(verbose_name="商品数量", default=1)
    total_price = models.DecimalField(verbose_name="订单总价", max_digits=14, decimal_places=2, default=0)
    discount_price = models.DecimalField(verbose_name="优惠价格", max_digits=10, decimal_places=2, default=0)
    freight_price = models.DecimalField(verbose_name="运费", max_digits=10, decimal_places=2, default=0)
    pay_price = models.DecimalField(verbose_name="实际支付价格", max_digits=14, decimal_places=2, default=0)

    order_remaining_time = models.DateTimeField(verbose_name="订单剩余时间", blank=True, null=True)

    courier_person = models.CharField(verbose_name="快递员", max_length=32, blank=True, null=True)
    courier_phone = models.CharField(verbose_name="快递员手机号", max_length=32, blank=True, null=True)
    courier_number = models.CharField(verbose_name="快递单号", max_length=128, blank=True, null=True)
    address = models.CharField(verbose_name="收货地址", max_length=255, blank=True, null=True)
    delivery_time = models.DateTimeField(verbose_name="发货时间", blank=True, null=True)
    source = models.IntegerField(choices=SOURCE_CHOICES, verbose_name="订单来源", default=1)

    # 商品快照 (下单时复制，防止商品修改影响历史订单)
    goods_name = models.CharField(verbose_name="商品名称快照", max_length=255)
    goods_spec = models.JSONField(verbose_name="商品规格快照", blank=True, null=True, default=dict)
    # 商品缩略图快照，方便列表页展示，不用联表查商品表
    goods_image = models.CharField(verbose_name="商品主图快照", max_length=255, blank=True, null=True)

    user_remark = models.CharField(verbose_name="用户备注", max_length=255, blank=True, null=True)
    admin_remark = models.CharField(verbose_name="后台备注", max_length=255, blank=True, null=True)

    is_deleted = models.BooleanField(default=False, verbose_name="是否删除")

    class Meta:
        db_table = "t_order"
        verbose_name = "订单表"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["user", "-create_time"]),  # 常用查询，查询用户的最近的订单
            models.Index(fields=["status", "-create_time"]),  # 订单状态查询
            models.Index(fields=["order_number"])  # 订单编号查询
        ]
        unique_together = [
            ["user", "order_number"]
        ]  # 订单编号和用户不能重复

    def __str__(self):
        return f"{self.order_number} - {self.user}"


class OrderLog(BaseModel):
    """ 订单操作日志模型 """

    # 操作类型选择
    ACTION_CHOICES = (
        (1, "创建订单"),
        (2, "支付成功"),
        (3, "商家发货"),
        (4, "确认收货"),
        (5, "取消订单"),
        (6, "修改价格"),
        (7, "修改地址"),
        (8, "后台备注"),
        (9, "系统超时"),
    )

    # 如果订单没了，日志通常也没意义
    order = models.ForeignKey("Order", verbose_name="关联订单", on_delete=models.CASCADE, related_name="order_logs",
                              db_index=True)

    # 如果是管理员操作，user 可以为空，operator_name 存管理员名字
    operator = models.ForeignKey(User, verbose_name="操作人", on_delete=models.SET_NULL, null=True, blank=True)
    operator_name = models.CharField(verbose_name="操作人名称(快照)", max_length=64, blank=True,
                                     null=True)  # 防止用户被删后日志看不清

    action = models.SmallIntegerField(choices=ACTION_CHOICES, verbose_name="操作类型")
    message = models.TextField(verbose_name="操作详情/变更内容", blank=True, null=True)

    ip_address = models.GenericIPAddressField(verbose_name="操作IP", protocol="both", null=True, blank=True)

    class Meta:
        db_table = "t_order_log"
        verbose_name = "订单操作日志"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]
        indexes = [
            models.Index(fields=["order", "-create_time"])
        ]

    def __str__(self):
        return f"订单 {self.order.order_number} - {self.get_action_display()} - {self.create_time}"
