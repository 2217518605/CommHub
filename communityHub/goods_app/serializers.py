import logging
import os

from rest_framework import serializers

from goods_app.models import Goods, GoodsComments, GoodsImage
from organization_app.models import Organization
from user_app.models import User

logger = logging.getLogger(__name__)


class GoodsImageSerializer(serializers.ModelSerializer):
    """ 商品图片返参序列化器 """

    class Meta:
        model = GoodsImage
        fields = ["id", "image", "sort_order"]


class MultiImageField(serializers.ListField):
    """支持同时上传多张图片的字段，修复 QueryDict.get() 只返回最后一张的问题"""

    def get_value(self, dictionary):
        if hasattr(dictionary, 'getlist'):
            return dictionary.getlist(self.field_name)
        return super().get_value(dictionary)


class GoodsCommonSerializer(serializers.ModelSerializer):
    """ 商品的通用入参序列化器(创建、更新) """

    images = MultiImageField(
        child=serializers.ImageField(),
        required=False,
        write_only=True,
        help_text="多张图片列表，第一张为主图，第二张为缩略图，其余为附加图片"
    )

    class Meta:
        model = Goods
        exclude = ("user", "organization")
        extra_kwargs = {
            "user": {"write_only": True},
            "organization": {"write_only": True},
            "big_img": {"required": False},
            "small_img": {"required": False},
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

    def _validate_image_format(self, image):
        ext = os.path.splitext(image.name)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".gif"]:
            raise serializers.ValidationError(f"图片格式不支持：{ext}，仅支持 jpg/png/gif")
        return image

    def _process_images(self, goods, images):
        """处理上传的多张图片：第一张→big_img，第二张→small_img，其余→GoodsImage"""
        if not images:
            return

        for idx, img in enumerate(images):
            self._validate_image_format(img)
            if idx == 0:
                goods.big_img = img
            elif idx == 1:
                goods.small_img = img
            else:
                GoodsImage.objects.create(goods=goods, image=img, sort_order=idx)

    def validate(self, data):
        """ 校验其他数据的合理性 """
        if data.get("number", 1) <= 0:
            logger.error("商品创建 商品数量必须大于0")
            raise serializers.ValidationError("商品数量必须大于0")

        price = data.get("price")
        if price is not None and price <= 0:
            logger.error("商品创建 商品价格必须大于0")
            raise serializers.ValidationError("商品价格必须大于0")

        images = data.get("images", [])
        for img in images:
            self._validate_image_format(img)

        return data

    def create(self, validated_data):
        images = validated_data.pop("images", [])
        instance = super().create(validated_data)
        if images:
            self._process_images(instance, images)
            instance.save(update_fields=["big_img", "small_img"])
        return instance

    def update(self, instance, validated_data):
        images = validated_data.pop("images", None)
        instance = super().update(instance, validated_data)
        if images is not None and len(images) > 0:
            self._process_images(instance, images)
            instance.save(update_fields=["big_img", "small_img"])
        return instance


class GoodsResponseSerializer(serializers.ModelSerializer):
    """ 商品通用返参序列化器  """
    organization_name = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    extra_images = GoodsImageSerializer(many=True, read_only=True)

    def get_organization_name(self, obj):
        return obj.organization.org_name if obj.organization_id else None

    def get_user_name(self, obj):
        return obj.user.username if obj.user_id else None

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

    parent = serializers.PrimaryKeyRelatedField(queryset=GoodsComments.objects.all(), required=False, allow_null=True)

    class Meta:
        model = GoodsComments
        fields = "__all__"
        extra_kwargs = {
            "user": {"required": False},
        }


class GoodsCommentsResponseSerializer(serializers.ModelSerializer):
    """ 商品评论返参序列化器 """

    goods_name = serializers.CharField(read_only=True, source="goods.name")
    user_name = serializers.CharField(read_only=True, source="user.username")
    user_avatar = serializers.SerializerMethodField()
    reply_to_id = serializers.IntegerField(read_only=True, source="parent_id", default=None)
    reply_to_user_name = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    def get_user_avatar(self, obj):
        try:
            return obj.user.avatar.url if obj.user.avatar else None
        except Exception:
            return None

    def get_reply_to_user_name(self, obj):
        if obj.parent_id and hasattr(obj, 'reply_to_username'):
            return obj.reply_to_username
        return None

    def get_is_liked(self, obj):
        liked_ids = self.context.get('liked_comment_ids', set())
        return obj.id in liked_ids

    user_id = serializers.IntegerField(read_only=True, source="user.id", default=None)

    class Meta:
        model = GoodsComments
        fields = ["id", "comment", "user_name", "user_id", "user_avatar", "reply_to_id", "reply_to_user_name",
                   "goods_name", "create_time", "like_num", "is_liked"]
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
