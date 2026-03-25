from django.db import models

from models.base import BaseModel
from user_app.models import User
from organization_app.models import Organization


class Goods(BaseModel):
    """ 商品模型 """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="所属组织",
                                     help_text="所属组织", blank=False, null=False, related_name="org_goods")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="发布者", related_name="user_goods")
    name = models.CharField(max_length=50, verbose_name="商品名称", help_text="商品名称", blank=False, null=False)
    price = models.DecimalField(max_digits=7, decimal_places=2, verbose_name="商品价格", help_text="商品价格",
                                blank=False, null=False)
    number = models.IntegerField(verbose_name="商品数量", help_text="商品数量", blank=False, null=False, default=0)
    desc = models.TextField(verbose_name="商品描述", help_text="商品描述", blank=True, null=True)
    big_img = models.ImageField(verbose_name="商品图片", help_text="商品图片", blank=True, null=True,
                                upload_to='goods_photos/', default='goods_photos/default_goods_photos.png')
    small_img = models.ImageField(verbose_name="商品缩略图", help_text="商品缩略图", blank=True, null=True,
                                  upload_to='goods_photos/', default='goods_photos/default_goods_photos.png')
    status = models.CharField(verbose_name="商品状态", help_text="商品状态", max_length=10,
                              choices=(('pending', '待审核'), ('normal', '已上架'), ('offshelf', '下架'),
                                       ('soldout', '售完')))
    sold_count = models.IntegerField(verbose_name="已售数量", help_text="已售数量", default=0)

    class Meta:
        db_table = "t_goods"
        verbose_name = "商品"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['status'])
        ]


class GoodsLog(BaseModel):
    """
    商品操作日志（审计日志）
    记录：创建 / 修改 / 删除
    """
    OPERATION_CHOICES = (
        ('create', '创建商品'),
        ('update', '修改商品'),
        ('delete', '删除商品'),
        ('sold', '商品售出'),
    )

    # 操作人
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="操作人")
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name="所属组织")

    goods_id = models.IntegerField(verbose_name="商品ID")
    goods_name = models.CharField(max_length=255, verbose_name="商品名称")

    operation_type = models.CharField(max_length=20, choices=OPERATION_CHOICES, verbose_name="操作类型")

    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="操作IP")

    # 备注（记录修改了什么）
    remark = models.TextField(blank=True, default="", verbose_name="操作备注/详情")

    class Meta:
        db_table = "t_goods_log"
        verbose_name = "商品操作日志"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.get_operation_display()} | {self.goods_name} | {self.user}"


class GoodsComments(BaseModel):
    """ 商品评论模型 """

    goods = models.ForeignKey(Goods, verbose_name="商品", help_text="商品", blank=False, null=False,
                              on_delete=models.CASCADE,
                              related_name='goods_comments')
    user = models.ForeignKey(User, verbose_name="用户", help_text="用户", blank=False, null=False,
                             on_delete=models.CASCADE,
                             related_name='user_comments')
    parent = models.ForeignKey('self', verbose_name="商品的父评论", help_text="商品的父评论", blank=True, null=True,
                               on_delete=models.CASCADE, related_name='replies')
    comment = models.TextField(verbose_name="评论", help_text="评论", blank=False, null=False)
    like_num = models.IntegerField(verbose_name="点赞数", help_text="点赞数", blank=False, null=False, default=0)

    # is_deleted = models.BooleanField(verbose_name="评论是否被删除", help_text="评论是否被删除", default=False)
    # deleted_by = models.ForeignKey(User, verbose_name="删除该评论的用户", help_text="删除该评论的用户", blank=True, null=True,
    #                                on_delete=models.SET_NULL)
    # deleted_time = models.DateTimeField(verbose_name="评论删除时间", help_text="评论删除时间", blank=True, null=True)

    def get_display_replies(self):
        """ 获取所有子级回复的前五条 """

        return self.replies.all()[:5]

    class Meta:
        db_table = "t_goods_comments"
        verbose_name = "用户评论"
        verbose_name_plural = verbose_name


class GoodsCommentsLog(BaseModel):
    """ 评论操作日志表（重点记录删除、屏蔽等敏感操作） """

    OPERATION_CHOICES = (
        ('delete', '用户自删'),
        ('admin_delete', '管理员删除'),
        ('ban', '屏蔽/折叠'),
    )

    comment = models.ForeignKey(GoodsComments, verbose_name="商品评论", help_text="商品评论", blank=True, null=True,
                                on_delete=models.SET_NULL, related_name='comment_log')
    operator = models.ForeignKey(User, verbose_name="操作用户", help_text="操作用户", blank=True, null=True,
                                 on_delete=models.SET_NULL, related_name='comment_log_user')
    # 组织允许为空，防止用户无组织时报错
    organization = models.ForeignKey(Organization, verbose_name="所属组织",
                                     on_delete=models.SET_NULL, null=True, blank=True)
    # 评论id快照,即使原评论没了，也能知道是哪个 ID
    comment_id_snapshot = models.IntegerField(verbose_name="评论ID快照", null=True, blank=True)
    # 评论内容快照,知道删了什么
    content_snapshot = models.TextField(verbose_name="评论内容快照", null=True, blank=True)
    #
    operation_type = models.CharField(max_length=20, choices=OPERATION_CHOICES, verbose_name="操作类型")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="操作IP")
    reason = models.TextField(verbose_name="操作原因", help_text="操作原因", blank=True, null=True)

    class Meta:
        db_table = "t_goods_comments_log"
        verbose_name = "商品评论操作日志"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]
