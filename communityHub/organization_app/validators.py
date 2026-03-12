import re

from rest_framework import serializers

def validate_chinese_name(value):
    """校验中文姓名"""
    value = value.strip()
    if not value:
        raise serializers.ValidationError("姓名不能为空")
    if not re.match(r'^[\u4e00-\u9fa5·]{2,10}$', value):
        raise serializers.ValidationError(
            "姓名仅支持2-10位汉字及中间点（·），例如：张三、欧阳·锋")


def validate_phone(value):
    """ 校验手机号 """
    if not value:
        raise serializers.ValidationError("手机号不能为空")
    if not re.match(r"^1[3-9]\d{9}$", value):
        raise serializers.ValidationError("请输入有效的手机号码（11 位数字，以 13-19 开头)")


def validate_image_format(value):
    """ 校验图片格式，仅支持 JPG、PNG、GIF 格式 """

    # 允许的图片扩展名
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    # 允许的图片 MIME 类型
    allowed_content_types = ['image/jpeg', 'image/png', 'image/gif']

    # 检查文件扩展名
    file_extension = value.name.split('.')[-1].lower()
    if '.' + file_extension not in allowed_extensions:
        raise serializers.ValidationError(
            f"不支持的图片格式。仅支持 JPG、PNG、GIF 格式，当前格式：{file_extension.upper()}")

    # 检查文件 MIME 类型
    content_type = value.content_type
    if content_type not in allowed_content_types:
        raise serializers.ValidationError(
            f"不支持的图片类型。仅支持 JPG、PNG、GIF 格式，当前类型：{content_type}")
