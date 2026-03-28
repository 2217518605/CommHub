import re

from rest_framework import serializers

from organization_app.models import Organization
from .validators import validate_chinese_name, validate_phone, validate_image_format


class ContactPersonField(serializers.Field):
    def to_internal_value(self, data):
        if isinstance(data, list):
            cleaned = []
            for item in data:
                if not isinstance(item, str):
                    raise serializers.ValidationError("联系人姓名必须是字符串")
                validate_chinese_name(item)
                cleaned.append(item.strip())
            if len(cleaned) == 0:
                raise serializers.ValidationError("联系人姓名不能为空")
            return ",".join(cleaned)
        if isinstance(data, str):
            value = data.strip()
            if not value:
                raise serializers.ValidationError("联系人姓名不能为空")
            validate_chinese_name(value)
            return value
        raise serializers.ValidationError("联系人姓名格式不正确")

    def to_representation(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return parts
        return []


class OrganizationRequestSerializer(serializers.ModelSerializer):
    """ 组织机构创建入参序列化器 """

    org_name = serializers.CharField(label="社区组织名称", help_text="社区组织名称", required=True,
                                     error_messages={'blank': '社区组织名称不能为空'})
    contact_person = ContactPersonField(required=True, help_text='联系人姓名列表，例如：["张三"] 或 ["张三", "李四"]')
    contact_phone = serializers.CharField(label="组织联系电话", help_text="组织联系电话", required=True,
                                          validators=[validate_phone])
    contact_email = serializers.EmailField(label="社区联系邮箱", help_text="社区联系邮箱", required=False)
    address = serializers.CharField(label="地址", help_text="地址", required=False)
    description = serializers.CharField(label="社区组织描述", help_text="社区组织描述", required=False)
    org_avatar = serializers.ImageField(
        label="组织头像",
        help_text="组织头像",
        required=False,
        validators=[validate_image_format]
    )

    class Meta:
        model = Organization
        fields = '__all__'


class OrganizationResponseSerializer(serializers.ModelSerializer):
    """ 组织机构出参序列化器 """

    id = serializers.IntegerField(label="社区组织ID", help_text="社区组织ID")
    org_name = serializers.CharField(label="社区组织名称", help_text="社区组织名称")
    contact_person = ContactPersonField()
    contact_phone = serializers.CharField(label="组织联系电话", help_text="组织联系电话")
    contact_email = serializers.EmailField(label="社区联系邮箱", help_text="社区联系邮箱")
    address = serializers.CharField(label="地址", help_text="地址")
    description = serializers.CharField(label="社区组织描述")
    org_avatar = serializers.ImageField(label="组织头像")

    class Meta:
        model = Organization
        fields = '__all__'


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    """ 组织机构入参序列化器 """

    org_name = serializers.CharField(label="社区组织名称", help_text="社区组织名称", required=False,
                                     error_messages={'blank': '社区组织名称不能为空'})
    contact_person = ContactPersonField(required=False, help_text='联系人姓名列表，例如：["张三"] 或 ["张三", "李四"]')
    contact_phone = serializers.CharField(label="组织联系电话", help_text="组织联系电话", required=False,
                                          validators=[validate_phone])
    contact_email = serializers.EmailField(label="社区联系邮箱", help_text="社区联系邮箱", required=False)
    address = serializers.CharField(label="地址", help_text="地址", required=False)
    description = serializers.CharField(label="社区组织描述", help_text="社区组织描述", required=False)
    org_avatar = serializers.ImageField(
        label="组织头像",
        help_text="组织头像",
        required=False,
        validators=[validate_image_format]
    )

    class Meta:
        model = Organization
        fields = '__all__'


class OrganizationDeleteSerializer(serializers.ModelSerializer):
    """ 删除组织机构入参序列化器 """

    id = serializers.IntegerField(label="社区组织ID", help_text="社区组织ID")

    class Meta:
        model = Organization
        fields = '__all__'
