import re

from rest_framework import serializers

from organization_app.models import Organization
from .validators import validate_chinese_name, validate_phone, validate_image_format


class OrganizationRequestSerializer(serializers.ModelSerializer):
    """ 组织机构创建入参序列化器 """

    org_name = serializers.CharField(label="社区组织名称", help_text="社区组织名称", required=True,
                                     error_messages={'blank': '社区组织名称不能为空'})
    contact_person = serializers.ListField(
        child=serializers.CharField(
            max_length=20,
            validators=[validate_chinese_name]
        ),
        required=True, allow_empty=True, min_length=1,
        help_text='联系人姓名列表，例如：["张三"] 或 ["张三", "李四"]')
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
    contact_person = serializers.CharField(label="组织联系人", help_text="组织联系人")
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
    contact_person = serializers.ListField(
        child=serializers.CharField(
            max_length=20,
            validators=[validate_chinese_name]
        ),
        required=False, allow_empty=True, min_length=1,
        help_text='联系人姓名列表，例如：["张三"] 或 ["张三", "李四"]')
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
