import logging

from django.shortcuts import get_object_or_404
from django.db import transaction
from django.conf import settings
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes

from config.decorators.common import api_doc, api_get, api_post, api_put, api_delete
from user_app.models import User
from organization_app.models import Organization
from goods_app.models import Goods, GoodsComments, GoodsLog, GoodsCommentsLog
from goods_app.serializers import GoodsCommentsRetrieveSerializer, GoodsCommentsResponseSerializer, \
    GoodsCommonSerializer, GoodsResponseSerializer, GoodsQueryByNameSerializer, GoodsCommentsSerializer
from config.help_tools import common_response
from config.authentication import IsAdmin, IsSuperAdmin, IsPublic, IsCommonUser
from config.help_tools import CommonPageNumberPagination
from config.serializers.base import EmptySerializer
from config.help_tools import get_client_ip

logger = logging.getLogger(__name__)


class GoodsRetrieveViewSet(ViewSet):
    permission_classes = [IsCommonUser]

    def get_permissions(self):
        """ 放开查看商品详情的权限,其他需要登录才能操作 """

        if self.action == "retrieve":
            """ 正常情况下未登录用户也可以查看商品详情的 """
            return [IsPublic()]
        return [permission() for permission in self.permission_classes]

    @api_doc(tags=["商品 获取单个商品详情"], query_serializer=GoodsCommentsRetrieveSerializer,
             response_body=GoodsCommentsResponseSerializer)
    @api_get
    def retrieve(self, request, pk):

        goods = get_object_or_404(Goods.objects.select_related('user', 'organization'), pk=pk)
        serializer = GoodsResponseSerializer(goods)
        logger.info(f'商品 获取成功：商品信息：{serializer.data}')
        return common_response(status=status.HTTP_200_OK, message="商品详情获取成功", data=serializer.data)

    @api_doc(tags=["商品 创建单个商品"], request_body=GoodsCommonSerializer, response_body=GoodsResponseSerializer)
    @api_post
    @transaction.atomic
    def create(self, request):

        user = request.user
        org = user.organization
        if not org:
            logger.warning(f'用户 {user.username} 没有组织,请加入组织，才允许发布商品')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有组织，请加入组织，才允许发布商品")

        serializer = GoodsCommonSerializer(data=request.data)
        if serializer.is_valid():
            goods = serializer.save(user=user, organization=org)

            # 创建商品操作日志
            GoodsLog.objects.create(goods_id=goods.id, goods_name=goods.name, operation_type="create", user=user,
                                    organization=org, ip_address=get_client_ip(request), remark="创建商品")

            logger.info(f'商品 创建成功：商品信息：{serializer.data}')
            return common_response(status=status.HTTP_201_CREATED, message="商品创建成功",
                                   data=GoodsResponseSerializer(goods).data)
        else:
            logger.error(f'商品 创建失败：商品信息：{serializer.errors}')
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品创建失败", data=serializer.errors)

    @api_doc(tags=["商品 修改单个商品"], request_body=GoodsCommonSerializer, response_body=GoodsResponseSerializer)
    @api_put
    def update(self, request, pk):

        goods = get_object_or_404(Goods.objects.select_related('user', 'organization'), pk=pk)

        if goods.user != request.user:
            logger.warning(f'用户 {request.user.username} 没有权限修改商品 {goods.name}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限修改商品")

        serializer = GoodsCommonSerializer(goods, data=request.data)
        if serializer.is_valid():
            good = serializer.save()

            GoodsLog.objects.create(goods_id=goods.id, goods_name=goods.name, operation_type="update",
                                    user=request.user,
                                    organization=goods.organization, ip_address=get_client_ip(request),
                                    remark="修改商品")

            logger.info(f'商品 修改成功：商品信息：{serializer.data}')
            return common_response(status=status.HTTP_200_OK, message="商品修改成功",
                                   data=GoodsResponseSerializer(good).data)
        else:
            logger.error(f'商品 修改失败：商品信息：{serializer.errors}')
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品修改失败", data=serializer.errors)

    @api_doc(tags=["商品 删除单个商品"], request_body=GoodsCommonSerializer, response_body=EmptySerializer)
    @api_delete
    @transaction.atomic
    def destroy(self, request, pk):

        goods = get_object_or_404(Goods.objects.select_related('user', 'organization'), pk=pk)

        if goods.user != request.user:
            logger.warning(f'用户 {request.user.username} 没有权限删除商品 {goods.name}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限删除商品")

        GoodsLog.objects.create(goods_id=goods.id, goods_name=goods.name, operation_type="delete", user=request.user,
                                organization=goods.organization, ip_address=get_client_ip(request),
                                remark="删除商品")

        goods.delete()
        logger.info(f'商品 删除成功：商品ID：{pk}')
        return common_response(status=status.HTTP_200_OK, message="商品删除成功")


class GoodsListViewSet(ViewSet):
    permission_classes = [IsPublic]
    pagination_class = CommonPageNumberPagination

    @api_doc(tags=["商品 通过关键词获取所有商品列表"], request_body=GoodsQueryByNameSerializer,
             response_body=GoodsResponseSerializer)
    @api_post
    def list_by_query_name(self, request):

        query_name = request.data.get("query_name")
        if query_name:
            goods_list = Goods.objects.select_related("user", "organization").filter(
                name__icontains=query_name).order_by('-create_time', '-id')
        else:
            goods_list = Goods.objects.select_related("user", "organization").order_by('-create_time', '-id')
        logger.info(f'商品 获取成功,商品条数为：{goods_list.count()}')

        paginator = self.pagination_class()
        pagination_data = paginator.paginate_queryset(goods_list, request)

        serializer = GoodsResponseSerializer(pagination_data, many=True)
        return paginator.get_paginated_response({
            "status": status.HTTP_200_OK,
            "message": "获取商品列表成功",
            "data": serializer.data
        })


class GoodsCommentsRetrieveViewSet(ViewSet):
    permission_classes = [IsCommonUser]

    @api_doc(tags=["商品评论 创建商品评论"], request_body=GoodsCommentsSerializer,
             response_body=GoodsCommentsResponseSerializer)
    @api_post
    @transaction.atomic
    def create(self, request):

        user = request.user
        org = user.organization

        serializer = GoodsCommentsSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(f'商品评论 创建商品评论失败：参数校验失败：{serializer.errors}')
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品评论创建失败,参数校验失败",
                                   data=serializer.errors)

        goods = serializer.validated_data.get("goods")
        parent = serializer.validated_data.get("parent")
        if parent and parent.goods_id != goods.id:
            logger.warning(f'商品评论 创建商品评论失败：回复的评论不属于该商品')
            return common_response(status=status.HTTP_400_BAD_REQUEST,
                                   message="商品评论创建失败,回复的评论不属于该商品", data=serializer.errors)

        comment = serializer.save(user=user, organization=org)
        logger.info(f'商品评论 创建成功：商品评论信息：{serializer.data}')
        return common_response(status=status.HTTP_201_CREATED, message="商品评论创建成功",
                               data=GoodsCommentsResponseSerializer(comment).data)

    @api_doc(tags=["商品评论 删除商品评论"], request_body=GoodsCommentsRetrieveSerializer,
             response_body=EmptySerializer)
    @api_delete
    @transaction.atomic
    def destroy(self, request, pk):

        current_user = request.user

        comment = get_object_or_404(GoodsComments.objects.select_related('user', 'goods',"user__organization"), pk=pk)

        is_admin = current_user.user_type in ["admin", "super_admin"]
        is_owner = (comment.user == current_user)

        if not (is_admin or is_owner):
            logger.warning(f'用户 {current_user.username} 没有权限删除商品评论 {comment.id}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限删除商品评论")

        if is_admin and not is_owner:
            op_type = "admin_delete"
            reason = "管理员强制执行删除"
            logger.warning(
                f"管理员：{current_user.username} 删除了用户：{comment.user.username} 的评论，评论的ID ：{comment.id}")
        else:
            op_type = "delete"
            reason = "用户自己删除"
            logger.info(f"用户：{current_user.username} 删除了评论，评论的ID ：{comment.id}")

        org = comment.user.organization if hasattr(comment.user, "organization") else None  # 防止用户没有组织

        # 记录管理员删除的日志
        GoodsCommentsLog.objects.create(comment=comment, operator=current_user, organization=org,
                                        comment_id_snapshot=comment.id, content_snapshot=comment.content[:500],
                                        operation_type=op_type, ip_address=get_client_ip(request), reason=reason)

        comment.delete()
        logger.info(f'商品评论 删除成功：商品评论ID：{pk}')
        return common_response(status=status.HTTP_200_OK, message="商品评论删除成功")


class GoodsCommentsListViewSet(ViewSet):
    permission_classes = [IsPublic]
    pagination_class = CommonPageNumberPagination

    @api_doc(tags=["商品评论 获取商品评论（子级评论一次展示五条）"], request_body=GoodsCommentsRetrieveSerializer,
             response_body=GoodsCommentsResponseSerializer)
    @api_post
    def list(self, request):

        # 传递 是否展开子级评论和父级评论的ID
        show_reply_comments = request.data.get("show_reply_comments")
        parent_id = request.data.get("id")

        goods_id = request.data.get("goods_id")

        # 查询当前商品下面的评论的子级评论
        if show_reply_comments and parent_id:
            parent_comment = get_object_or_404(GoodsComments.objects.select_related('user', 'goods', "organization"),
                                               pk=parent_id)

            try:
                target_goods_id = int(goods_id)
            except (ValueError, TypeError):
                return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品 ID 格式错误")

            if parent_comment.goods_id != target_goods_id:
                logger.warning(f'商品评论 获取商品子级评论失败：父级商品评论不属于该商品')
                return common_response(status=status.HTTP_400_BAD_REQUEST,
                                       message="商品评论获取失败,父级商品评论不属于该商品")

            comments_replies_list = parent_comment.replies.select_related('user', 'goods', "organization").order_by(
                '-create_time', '-id')[:settings.MAX_REPLY_DISPLAY_COUNT]
            return common_response(status=status.HTTP_200_OK, message="获取商品子级评论成功",
                                   data=GoodsCommentsResponseSerializer(comments_replies_list, many=True).data)

        # 获取商品评论（一次50条，获取更多就刷新一次接口）
        comments_list = GoodsComments.objects.select_related('user', 'goods', "organization").filter(goods_id=goods_id,
                                                                                                     parent=None).order_by(
            '-create_time', '-id')[:settings.MAX_COMMENT_COUNT]

        logger.info(f'商品 获取成功,商品条数为：{comments_list.count()}')
        paginator = self.pagination_class()
        pagination_data = paginator.paginate_queryset(comments_list, request)
        serializer = GoodsCommentsResponseSerializer(pagination_data, many=True)
        return paginator.get_paginated_response({
            "status": status.HTTP_200_OK,
            "message": "获取商品评论成功",
            "data": serializer.data
        })
