"""
基础序列化器类
"""
from rest_framework import serializers


class EmptySerializer(serializers.Serializer):
    """空序列化器，用于不需要响应体的接口文档定义"""
    pass

