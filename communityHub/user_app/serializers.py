from rest_framework import serializers

from user_app.models import User


class UserRegisterSerializer(serializers.ModelSerializer):
    """ 用户注册序列化器 """

    password_confirm = serializers.CharField(write_only=True, max_length=256)

    class Meta:
        model = User
        fields = [
            'account', 'password', 'password_confirm',
            'mobile', 'email', 'username'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 3, 'max_length': 20},
            'account': {'min_length': 3, 'max_length': 20},
            'username': {'required': False, 'allow_blank': True}
        }

    def validate(self, data):
        """ 验证密码 """

        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError("两次输入的密码不一致")
        return data

    def create(self, validated_data):
        """ 让模型的默认值生效 """

        if not validated_data.get('username'):
            validated_data['username'] = None  # 触发模型默认或后续生成
        user = User.objects.create(**validated_data)
        return user


class UserLoginSerializer(serializers.ModelSerializer):
    """ 用户登录序列化器 """

    account = serializers.CharField(max_length=20, help_text="用户账号", verbose_name="用户账号", null=False,
                                    blank=False, )
    password = serializers.CharField(write_only=True, max_length=256)
    remember = serializers.BooleanField(default=False, help_text="记住登录状态", verbose_name="记住登录状态")

    class Meta:
        model = User
        fields = [
            'account', 'password',
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
            'username', 'mobile', 'email', 'avatar', 'birth_date', 'id_card', 'balance', "organization_id", "password"]


class UserDeleteSerializer(serializers.ModelSerializer):
    """ 用户删除序列化器 """

    class Meta:
        model = User
        fields = ['id']


class UserResponseSerializer(serializers.ModelSerializer):
    """ 用户返回序列化器 """

    class Meta:
        model = User
        fields = [
            'id', 'username', "account", "password", 'mobile', 'email', 'avatar', 'birth_date', 'id_card', 'balance',
            "organization_id",
            "is_active", "is_staff", "user_type", "last_login"
        ]
