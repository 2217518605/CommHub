from django.db import models

from models.base import BaseModel
from user_app.models import User
from organization_app.models import Organization
from goods_app.models import Goods


class Order(BaseModel):
    """ 订单模型 """

    STATUS_WAIT_PAY = 1
    STATUS_WAIT_DELIVER = 2
    STATUS_WAIT_RECEIVE = 3
    STATUS_WAIT_COMMENT = 4
    STATUS_FINISHED = 5
    STATUS_CANCELLED = 6

    ORDER_STATUS_CHOICES = (
        (STATUS_WAIT_PAY, "待付款"),
        (STATUS_WAIT_DELIVER, "待发货"),
        (STATUS_WAIT_RECEIVE, "待收货"),
        (STATUS_WAIT_COMMENT, "待评价"),
        (STATUS_FINISHED, "已完成"),
        (STATUS_CANCELLED, "已取消"),
    )

    PAY_METHOD_ALIPAY = 1
    PAY_METHOD_WECHAT = 2
    PAY_METHOD_CASH_ON_DELIVERY = 3

    PAY_METHOD_CHOICES = (
        (PAY_METHOD_ALIPAY, "支付宝"),
        (PAY_METHOD_WECHAT, "微信"),
        (PAY_METHOD_CASH_ON_DELIVERY, "货到付款"),
    )

    SOURCE_WECHAT_MINI_PROGRAM = 1
    SOURCE_H5 = 2
    SOURCE_APP = 3
    SOURCE_ADMIN = 4

    SOURCE_CHOICES = (
        (SOURCE_WECHAT_MINI_PROGRAM, "微信小程序"),
        (SOURCE_H5, "H5"),
        (SOURCE_APP, "App"),
        (SOURCE_ADMIN, "后台录入"),
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

    status = models.IntegerField(choices=ORDER_STATUS_CHOICES, verbose_name="订单状态", default=STATUS_WAIT_PAY, blank=False,
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
    source = models.IntegerField(choices=SOURCE_CHOICES, verbose_name="订单来源", default=SOURCE_WECHAT_MINI_PROGRAM)

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
    ACTION_CREATE_ORDER = 1
    ACTION_PAY_SUCCESS = 2
    ACTION_DELIVER = 3
    ACTION_CONFIRM_RECEIVE = 4
    ACTION_CANCEL_ORDER = 5
    ACTION_UPDATE_PRICE = 6
    ACTION_UPDATE_ADDRESS = 7
    ACTION_ADMIN_REMARK = 8
    ACTION_SYSTEM_TIMEOUT = 9

    ACTION_CHOICES = (
        (ACTION_CREATE_ORDER, "创建订单"),
        (ACTION_PAY_SUCCESS, "支付成功"),
        (ACTION_DELIVER, "商家发货"),
        (ACTION_CONFIRM_RECEIVE, "确认收货"),
        (ACTION_CANCEL_ORDER, "取消订单"),
        (ACTION_UPDATE_PRICE, "修改价格"),
        (ACTION_UPDATE_ADDRESS, "修改地址"),
        (ACTION_ADMIN_REMARK, "后台备注"),
        (ACTION_SYSTEM_TIMEOUT, "系统超时"),
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
