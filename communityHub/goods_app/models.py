from django.db import models

from models.base import BaseModel
from user_app.models import User
from organization_app.models import Organization


class Goods(BaseModel):
    """ 商品模型 """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="所属组织",
                                     help_text="所属组织", blank=False, null=False,related_name="org_goods")
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


class GoodsComments(BaseModel):
    """ 商品评论模型 """

    goods = models.ForeignKey(Goods, verbose_name="商品", help_text="商品", blank=False, null=False,
                              on_delete=models.CASCADE,
                              related_name='goods_comments')
    user = models.ForeignKey(User, verbose_name="用户", help_text="用户", blank=False, null=False,
                             on_delete=models.CASCADE,
                             related_name='user_comments')
    comment = models.TextField(verbose_name="评论", help_text="评论", blank=False, null=False)
    like = models.IntegerField(verbose_name="点赞数", help_text="点赞数", blank=False, null=False, default=0)
    reply = models.TextField(verbose_name="回复", help_text="回复", blank=True, null=True)
    comment_level = models.IntegerField(verbose_name="评论层级", help_text="评论层级", blank=False, null=False,
                                        default=1)

    class Meta:
        db_table = "t_goods_comments"
        verbose_name = "用户评论"
        verbose_name_plural = verbose_name
