import logging

from rest_framework import serializers

from user_app.models import User
from organization_app.models import Organization

logger = logging.getLogger(__name__)


class UserRegisterSerializer(serializers.ModelSerializer):
    """ 用户注册序列化器 """

    password_confirm = serializers.CharField(write_only=True, max_length=256)
    organization_id = serializers.IntegerField(required=False, allow_null=True, help_text="用户关联的组织ID")
    admin_secret = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=64, help_text="管理员注册密钥")

    class Meta:
        model = User
        fields = [
            'account', 'password', 'password_confirm', "birth_date", "id_card", "balance",
            'mobile', 'email', 'username', "organization_id", "is_staff", "user_type", "admin_secret"
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 3, 'max_length': 20},
            'account': {'min_length': 3, 'max_length': 20},
            'username': {'required': False, 'allow_blank': True}
        }

    def validate(self, data):
        """ 验证密码和管理员密钥 """

        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError("两次输入的密码不一致")

        user_type = data.get("user_type")
        if user_type == "admin":
            secret = data.get("admin_secret") or ""
            if secret != "admin123456":
                logger.info("用户 管理员创建失败，请填写正确的密钥！")
                raise serializers.ValidationError("管理员密钥不正确")
        return data

    def create(self, validated_data):

        # 移除不需要存入数据库的字段
        validated_data.pop('password_confirm', None)
        validated_data.pop('admin_secret', None)

        # username 为空
        if not validated_data.get('username'):
            validated_data['username'] = "默认用户"

        org_id = validated_data.get('organization_id')
        if org_id:
            try:
                org = Organization.objects.get(id=org_id)
                validated_data['organization'] = org
            except Organization.DoesNotExist:
                raise serializers.ValidationError("组织不存在")

        # 手动创建实例（不使用 .create()）
        user = User(**validated_data)
        user.save()  # 触发 save() 中的密码加密
        return user


class UserLoginSerializer(serializers.ModelSerializer):
    """ 用户登录序列化器 """

    account = serializers.CharField(max_length=20, help_text="用户账号")
    password = serializers.CharField(write_only=True, max_length=256)
    remember = serializers.BooleanField(default=False, help_text="记住登录状态")

    class Meta:
        model = User
        fields = [
            'account', 'password', 'remember'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 3, 'max_length': 20},
            'account': {'min_length': 3, 'max_length': 20},
        }


class UserUpdateSerializer(serializers.ModelSerializer):
    """ 用户更新序列化器 """

    class Meta:
        model = User
        fields = [
            'username', 'mobile', 'email', 'avatar', 'birth_date', 'id_card', 'balance', "organization", "password"]

    def validate_birth_date(self, value):
        if value == '' or (isinstance(value, str) and not value.strip()):
            return None
        return value

    def validate_id_card(self, value):
        if value == '' or (isinstance(value, str) and not value.strip()):
            return None
        return value


class UserDeleteSerializer(serializers.ModelSerializer):
    """ 用户删除序列化器 """

    class Meta:
        model = User
        fields = ['id']


class UserResponseSerializer(serializers.ModelSerializer):
    """ 用户返回序列化器 """
    organization_name = serializers.SerializerMethodField()

    def get_organization_name(self, obj):
        return obj.organization.org_name if obj.organization_id else None

    class Meta:
        model = User
        fields = [
            'id', 'username', "account", "password", 'mobile', 'email', 'avatar', 'birth_date', 'id_card', 'balance',
            "organization_id", "organization_name",
            "is_active", "is_staff", "user_type", "last_login"
        ]


class UserQueryByNameSerializer(serializers.Serializer):
    """ 通过关键词查找用户 """

    query_name = serializers.CharField(help_text="用户名关键字", allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = "__all__"
