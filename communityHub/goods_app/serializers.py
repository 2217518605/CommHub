import logging

from rest_framework import serializers

from goods_app.models import Goods, GoodsComments
from organization_app.models import Organization
from user_app.models import User

logger = logging.getLogger(__name__)


class GoodsCommonSerializer(serializers.ModelSerializer):
    """ 商品的通用入参序列化器(创建、更新) """

    class Meta:
        model = Goods
        exclude = ("user", "organization")
        extra_kwargs = {
            "user": {"write_only": True},
            "organization": {"write_only": True}
        }

    def validate_organization_id(self, value):
        """ 校验组织ID的存在性 """

        if not Organization.objects.filter(id=value).exists():
            logger.error("商品创建 组织不存在")
            raise serializers.ValidationError("组织不存在")
        return value

    def validate_user_id(self, value):
        """ 校验用户ID的存在性 """

        if not User.objects.filter(id=value).exists():
            logger.error("商品创建 用户不存在")
            raise serializers.ValidationError("用户不存在")
        return value

    def validate(self, data):
        """ 校验其他数据的合理性 """

        if data["number"] <= 0:
            logger.error("商品创建 商品数量必须大于0")
            raise serializers.ValidationError("商品数量必须大于0")

        if data["price"] <= 0:
            logger.error("商品创建 商品价格必须大于0")
            raise serializers.ValidationError("商品价格必须大于0")

        if data["sold_count"] < 0:
            logger.error("商品创建 已售数量必须大于等于0")
            raise serializers.ValidationError("已售数量必须大于等于0")

        allow_img_types = [".jpg", ".png", ".gif", ".jpeg"]

        print(type(data))

        if data.get("big_img") and data.get("small_img"):
            if data["big_img"].split(".")[-1] or data["small_img"].split(".")[-1] not in allow_img_types:
                logger.error("商品创建 图片格式错误")
                raise serializers.ValidationError("图片格式错误")

        return data


class GoodsResponseSerializer(serializers.ModelSerializer):
    """ 商品通用返参序列化器  """

    class Meta:
        model = Goods
        fields = "__all__"


class GoodsGetDeleteSerializer(serializers.ModelSerializer):
    """ 获取单个商品或者删除单个商品的通用序列化器 """

    class Meta:
        model = Goods
        fields = ["id"]


class GoodsQueryByNameSerializer(serializers.ModelSerializer):
    """ 根据商品名称查询商品通用序列化器 """

    query_name = serializers.CharField(help_text="商品名称关键字", allow_blank=True, allow_null=True)

    class Meta:
        model = Goods
        fields = ["query_name"]


class GoodsCommentsSerializer(serializers.ModelSerializer):
    """ 商品评论序列化器 """

    class Meta:
        model = GoodsComments
        fields = "__all__"


class GoodsCommentsResponseSerializer(serializers.ModelSerializer):
    """ 商品评论返参序列化器 """

    goods_name = serializers.CharField(write_only=True, help_text="评论的商品名称", source="goods.name")
    user_name = serializers.CharField(write_only=True, help_text="评论的用户名称", source="user.name")

    class Meta:
        model = GoodsComments
        fields = "__all__"
        extra_kwargs = {
            "goods": {"write_only": True},
            "user": {"write_only": True}
        }


class GoodsCommentsRetrieveSerializer(serializers.ModelSerializer):
    """ 获取商品评论 """

    show_reply_comments = serializers.BooleanField(help_text="是否显示回复的评论", default=False)
    goods_id = serializers.IntegerField(help_text="商品ID", write_only=True, required=True)
    id = serializers.IntegerField(help_text="父级评论ID", write_only=True, required=False)

    class Meta:
        model = GoodsComments
        fields = ["id", "show_reply_comments", "goods_id"]

class GoodsCommentsIncreaseLikeNumSerializer(serializers.ModelSerializer):
    """ 评论点赞 """

    comment_id = serializers.IntegerField(help_text="评论ID", write_only=True, required=True)
    is_increase_like_num = serializers.BooleanField(help_text="是否点赞", default=True)
    is_decrease_like_num = serializers.BooleanField(help_text="是否取消点赞", default=False)

    class Meta:
        model = GoodsComments
        fields = ["comment_id", "is_increase_like_num","is_decrease_like_num"]
