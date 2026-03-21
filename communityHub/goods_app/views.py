import logging

from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import permission_classes

from config.decorators.common import api_doc, api_get, api_post, api_put, api_delete
from user_app.models import User
from organization_app.models import Organization
from goods_app.models import Goods, GoodsComments
from goods_app.serializers import GoodsCommentsRetrieveSerializer, GoodsCommentsResponseSerializer, \
    GoodsCommonSerializer, GoodsResponseSerializer
from config.help_tools import common_response

logger = logging.getLogger(__name__)


class GoodsRetrieveViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """ 放开查看商品详情的权限,其他需要登录才能操作 """

        if getattr(self, "action", None) == "retrieve":
            """ 正常情况下未登录用户也可以查看商品详情的 """
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    @api_doc(tags=["商品 获取单个商品详情"], request_body=GoodsCommentsRetrieveSerializer,
             response_body=GoodsCommentsResponseSerializer)
    @api_get
    def retrieve(self, request, pk):

        goods = get_object_or_404(Goods, pk=pk)
        serializer = GoodsResponseSerializer(goods)
        logger.info(f'商品 获取成功：商品信息：{serializer.data}')
        return common_response(status=status.HTTP_200_OK, message="商品详情获取成功", data=serializer.data)

    @api_doc(tags=["商品 创建单个商品"], request_body=GoodsCommonSerializer, response_body=GoodsResponseSerializer)
    @api_post
    def create(self, request):

        serializer = GoodsCommonSerializer(data=request.data)
        user = request.user
        org = user.organization
        if not org:
            logger.error(f'用户 {user.username} 没有组织,请加入组织，才允许发布商品')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有组织，请加入组织，才允许发布商品")

        serializer = GoodsCommonSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user, organization=org)
            logger.info(f'商品 创建成功：商品信息：{serializer.data}')
            return common_response(status=status.HTTP_201_CREATED, message="商品创建成功", data=serializer.data)
        else:
            logger.error(f'商品 创建失败：商品信息：{serializer.errors}')
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品创建失败", data=serializer.errors)

    @api_doc(tags=["商品 修改单个商品"], request_body=GoodsCommonSerializer, response_body=GoodsResponseSerializer)
    @api_put
    def update(self, request, pk):

        goods = get_object_or_404(Goods, pk=pk)

        if goods.user != request.user:
            logger.error(f'用户 {request.user.username} 没有权限修改商品 {goods.name}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限修改商品")

        serializer = GoodsCommonSerializer(goods, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f'商品 修改成功：商品信息：{serializer.data}')
            return common_response(status=status.HTTP_200_OK, message="商品修改成功", data=serializer.data)
        else:
            logger.error(f'商品 修改失败：商品信息：{serializer.errors}')
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品修改失败", data=serializer.errors)

    @api_doc(tags=["商品 删除单个商品"], request_body=GoodsCommonSerializer, response_body=GoodsResponseSerializer)
    @api_delete
    def destroy(self, request, pk):

        goods = get_object_or_404(Goods, pk=pk)

        if goods.user != request.user:
            logger.error(f'用户 {request.user.username} 没有权限删除商品 {goods.name}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限删除商品")

        goods.delete()
        logger.info(f'商品 删除成功：商品ID：{pk}')
        return common_response(status=status.HTTP_200_OK, message="商品删除成功")
