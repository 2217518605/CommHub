import logging

# from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F
from django.conf import settings
from django.core.cache import cache
from rest_framework.viewsets import ViewSet
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from config.decorators.common import api_doc, api_get, api_post, api_put, api_delete
from user_app.models import User
from goods_app.models import Goods, GoodsComments, GoodsLog, GoodsCommentsLog, CommentLike
from goods_app.serializers import GoodsCommentsRetrieveSerializer, GoodsCommentsResponseSerializer, \
    GoodsCommonSerializer, GoodsResponseSerializer, GoodsQueryByNameSerializer, GoodsCommentsSerializer, \
    GoodsCommentsIncreaseLikeNumSerializer
from config.help_tools import common_response
from config.authentication import IsPublic, IsCommonUser
from config.help_tools import CommonPageNumberPagination
from config.serializers.base import EmptySerializer
from config.help_tools import get_client_ip, get_object_or_404

logger = logging.getLogger(__name__)


def _goods_search_cache_key(query_name, page_number, page_size, organization_id):
    """构造商品搜索缓存键"""

    version = cache.get(getattr(settings, "GOODS_HOT_CACHE_VERSION_KEY", "goods:hot:version"), 1)
    normalized_query = (query_name or "").strip().lower()
    prefix = getattr(settings, "GOODS_HOT_QUERY_CACHE_PREFIX", "goods:hot:query")
    return f"{prefix}:{version}:org{organization_id}:{normalized_query}:p{page_number}:s{page_size}"


def _page_size_from_request(request):
    try:
        return int(request.data.get("page_size") or CommonPageNumberPagination.page_size)
    except (TypeError, ValueError):
        return CommonPageNumberPagination.page_size


def _invalidate_goods_hot_cache():
    """通过版本号失效热门商品搜索缓存"""

    version_key = getattr(settings, "GOODS_HOT_CACHE_VERSION_KEY", "goods:hot:version")
    try:
        cache.incr(version_key)
    except ValueError:
        cache.set(version_key, 2)


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

        goods = get_object_or_404(Goods.objects.select_related('user', 'organization').prefetch_related('extra_images'),
                                  msg="要获取的商品不存在", pk=pk)
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
            _invalidate_goods_hot_cache()

            # 创建商品操作日志
            GoodsLog.objects.create(goods_id=goods.id, goods_name=goods.name, operation_type="create", user=user,
                                    organization=org, ip_address=get_client_ip(request), remark="创建商品")

            logger.info(f'商品 创建成功：商品信息：{serializer.data}')
            return common_response(status=status.HTTP_201_CREATED, message="商品创建成功",
                                   data=GoodsResponseSerializer(goods).data)
        else:
            logger.error(f'商品 创建失败：商品信息：{serializer.errors}', exc_info=True)
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品创建失败", data=serializer.errors)

    @api_doc(tags=["商品 修改单个商品"], request_body=GoodsCommonSerializer, response_body=GoodsResponseSerializer)
    @api_put
    def update(self, request, pk):

        goods = get_object_or_404(Goods.objects.select_related('user', 'organization').prefetch_related('extra_images'),
                                  msg="要更新的商品不存在", pk=pk)

        if goods.user != request.user:
            logger.warning(f'用户 {request.user.username} 没有权限修改商品 {goods.name}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限修改商品")

        serializer = GoodsCommonSerializer(goods, data=request.data)
        if serializer.is_valid():
            good = serializer.save()
            _invalidate_goods_hot_cache()

            GoodsLog.objects.create(goods_id=goods.id, goods_name=goods.name, operation_type="update",
                                    user=request.user,
                                    organization=goods.organization, ip_address=get_client_ip(request),
                                    remark="修改商品")

            logger.info(f'商品 修改成功：商品信息：{serializer.data}')
            return common_response(status=status.HTTP_200_OK, message="商品修改成功",
                                   data=GoodsResponseSerializer(good).data)
        else:
            logger.error(f'商品 修改失败：商品信息：{serializer.errors}', exc_info=True)
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品修改失败", data=serializer.errors)

    @api_doc(tags=["商品 删除单个商品"], request_body=GoodsCommonSerializer, response_body=EmptySerializer)
    @api_delete
    @transaction.atomic
    def destroy(self, request, pk):

        goods = get_object_or_404(Goods.objects.select_related('user', 'organization').prefetch_related('extra_images'),
                                  msg="要删除的商品不存在", pk=pk)

        if goods.user != request.user:
            logger.warning(f'用户 {request.user.username} 没有权限删除商品 {goods.name}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限删除商品")

        GoodsLog.objects.create(goods_id=goods.id, goods_name=goods.name, operation_type="delete", user=request.user,
                                organization=goods.organization, ip_address=get_client_ip(request),
                                remark="删除商品")

        goods.delete()
        _invalidate_goods_hot_cache()
        logger.info(f'商品 删除成功：商品ID：{pk}')
        return common_response(status=status.HTTP_200_OK, message="商品删除成功")


class GoodsListViewSet(ViewSet):
    permission_classes = [IsCommonUser]
    pagination_class = CommonPageNumberPagination

    @api_doc(tags=["商品 通过关键词获取所属组织商品列表"], request_body=GoodsQueryByNameSerializer,
             response_body=GoodsResponseSerializer)
    @api_post
    def list_by_query_name(self, request):

        user = request.user
        org = getattr(user, "organization", None)
        if not org:
            logger.warning(f'商品 用户 {user.username} 未加入组织，无法查看商品列表')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="请先加入组织，才能查看商品列表")

        query_name = request.data.get("query_name")
        page_number = request.data.get("page", 1)
        page_size = _page_size_from_request(request)
        cache_key = _goods_search_cache_key(query_name, page_number, page_size, org.id)
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.info(f'商品 搜索命中缓存：query_name={query_name}, page={page_number}, org={org.id}')
            if 'status' in cached_response:
                cached_response = cached_response.get('data', cached_response)
            return common_response(status=status.HTTP_200_OK, message="获取商品列表成功", data=cached_response)

        goods_queryset = Goods.objects.select_related("user", "organization").prefetch_related("extra_images").filter(
            status=Goods.STATUS_NORMAL, organization=org)
        if query_name:
            goods_queryset = goods_queryset.filter(name__icontains=query_name)

        goods_list = goods_queryset.order_by('-is_hot', '-create_time', '-id')
        logger.info(f'商品 搜索查询成功,商品条数为：{goods_list.count()}')

        paginator = self.pagination_class()
        pagination_data = paginator.paginate_queryset(goods_list, request)
        serializer = GoodsResponseSerializer(pagination_data, many=True)
        response_body = paginator.get_paginated_response(serializer.data)
        cache.set(cache_key, response_body.data.get('data'), timeout=getattr(settings, "GOODS_HOT_CACHE_TIMEOUT", 300))
        return response_body


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
        elif serializer.is_valid():
            goods = serializer.validated_data.get("goods")
            parent = serializer.validated_data.get("parent")
            logger.info(f'商品评论 创建请求：goods_id={goods.id if goods else None}, parent_id={parent.id if parent else None}, parent_user={parent.user.username if parent and parent.user else None}, comment={serializer.validated_data.get("comment")[:50]}')
            if parent and parent.goods_id != goods.id:
                logger.warning(f'商品评论 创建商品评论失败：回复的评论不属于该商品')
                return common_response(status=status.HTTP_400_BAD_REQUEST,
                                       message="商品评论创建失败,回复的评论不属于该商品", data=serializer.errors)

            comment = serializer.save(user=user)
            logger.info(f'商品评论 创建成功：id={comment.id}, parent_id={comment.parent_id}, comment={comment.comment[:50]}')
            return common_response(status=status.HTTP_201_CREATED, message="商品评论创建成功",
                                   data=GoodsCommentsResponseSerializer(comment).data)

    @api_doc(tags=["商品评论 删除商品评论"], request_body=GoodsCommentsRetrieveSerializer,
             response_body=EmptySerializer)
    @api_delete
    @transaction.atomic
    def destroy(self, request, pk):

        current_user = request.user

        comment = get_object_or_404(GoodsComments.objects.select_related('user', 'goods', "user__organization"), pk=pk)

        is_admin = current_user.user_type in ["admin", "super_admin"]
        is_owner = (comment.user == current_user)

        if not (is_admin or is_owner):
            logger.warning(f'用户 {current_user.username} 没有权限删除商品评论 {comment.id}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限删除商品评论")

        if is_admin and is_owner:
            op_type = "admin_delete"
            reason = "管理员本人删除自己的评论"
            logger.warning(
                f"管理员：{current_user.username} 删除了自己的：{comment.user.username} 的评论，评论的ID ：{comment.id}")
        elif is_admin and not is_owner:
            op_type = "admin_delete"
            reason = "管理员强制执行删除"
            logger.warning(
                f"管理员：{current_user.username} 强行删除了用户：{comment.user.username} 的评论，评论的ID ：{comment.id}"
            )
        else:
            op_type = "delete"
            reason = "用户自己删除"
            logger.info(f"用户：{current_user.username} 删除了评论，评论的ID ：{comment.id}")

        org = comment.user.organization if hasattr(comment.user, "organization") else None  # 防止用户没有组织

        # 记录管理员删除的日志
        GoodsCommentsLog.objects.create(comment=comment, operator=current_user, organization=org,
                                        comment_id_snapshot=comment.id, content_snapshot=comment.comment[:500],
                                        operation_type=op_type, ip_address=get_client_ip(request), reason=reason)

        comment.delete()
        logger.info(f'商品评论 删除成功：商品评论ID：{pk}')
        return common_response(status=status.HTTP_200_OK, message="商品评论删除成功")


class GoodsCommentsCascadeDeleteViewSet(ViewSet):
    """级联删除评论及其所有子回复"""
    permission_classes = [IsAuthenticated]

    @api_doc(tags=["商品评论 级联删除评论"], request_body=GoodsCommentsRetrieveSerializer,
             response_body=EmptySerializer)
    @api_delete
    @transaction.atomic
    def cascade_destroy(self, request, pk):

        current_user = request.user
        comment = get_object_or_404(GoodsComments.objects.select_related('user', 'goods', "user__organization"), pk=pk)

        is_admin = current_user.user_type in ["admin", "super_admin"]
        is_owner = (comment.user == current_user)

        if not (is_admin or is_owner):
            logger.warning(f'用户 {current_user.username} 没有权限删除商品评论 {comment.id}')
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户没有权限删除商品评论")

        def get_all_descendant_ids(comment_id):
            ids = [comment_id]
            children = GoodsComments.objects.filter(parent_id=comment_id)
            for child in children:
                ids.extend(get_all_descendant_ids(child.id))
            return ids

        all_ids = get_all_descendant_ids(pk)
        comments_to_delete = GoodsComments.objects.filter(id__in=all_ids)

        for cmt in comments_to_delete:
            org = cmt.user.organization if hasattr(cmt.user, "organization") else None
            GoodsCommentsLog.objects.create(
                comment=cmt, operator=current_user, organization=org,
                comment_id_snapshot=cmt.id, content_snapshot=cmt.comment[:500] if cmt.comment else "",
                operation_type="cascade_delete", ip_address=get_client_ip(request),
                reason=f"级联删除，父评论ID：{pk}"
            )
            
        deleted_total, deleted_detail = comments_to_delete.delete()
        logger.info(f'商品评论 级联删除成功：父评论ID={pk}, 删除总数={deleted_total}')
        return common_response(status=status.HTTP_200_OK, message=f"删除成功，共删除 {deleted_total} 条评论")


class GoodsCommentsListViewSet(ViewSet):
    permission_classes = [IsPublic]
    pagination_class = CommonPageNumberPagination

    @api_doc(tags=["商品评论 获取商品评论"], request_body=GoodsCommentsRetrieveSerializer,
             response_body=GoodsCommentsResponseSerializer)
    @api_post
    def list(self, request):

        goods_id = request.data.get("goods_id")

        try:
            target_goods_id = int(goods_id)
        except (ValueError, TypeError):
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="商品 ID 格式错误")

        # 返回该商品下所有评论，包括回复
        comments_list = GoodsComments.objects.select_related('user', 'goods').filter(
            goods_id=target_goods_id
        ).annotate(
            reply_to_username=F('parent__user__username')
        ).order_by('-create_time', '-id')[:settings.MAX_COMMENT_COUNT]

        logger.info(f'商品评论 获取成功,评论条数为：{comments_list.count()}')

        # 获取当前用户已点赞的评论ID集合
        liked_comment_ids = set()
        if request.user and request.user.is_authenticated:
            comment_ids = [c.id for c in comments_list]
            liked_comment_ids = set(
                CommentLike.objects.filter(user=request.user, comment_id__in=comment_ids)
                .values_list('comment_id', flat=True)
            )

        paginator = self.pagination_class()
        pagination_data = paginator.paginate_queryset(comments_list, request)
        serializer = GoodsCommentsResponseSerializer(
            pagination_data, many=True,
            context={'liked_comment_ids': liked_comment_ids}
        )
        return paginator.get_paginated_response(serializer.data)


class GoodsCommentsLikeNumViewSet(ViewSet):
    perimissions = [IsCommonUser]

    @api_doc(tags=["商品评论 点赞/取消点赞"], request_body=GoodsCommentsIncreaseLikeNumSerializer,
             response_body=EmptySerializer)
    @api_post
    def increase_like_num(self, request):

        good_comment_id = request.data.get("comment_id")
        user = request.user

        comment = get_object_or_404(GoodsComments.objects.select_related('user', 'goods'), msg="商品评论不存在",
                                    pk=good_comment_id)

        # 检查是否已点赞：已点则取消，未点则点赞
        existing_like = CommentLike.objects.filter(user=user, comment=comment).first()
        if existing_like:
            existing_like.delete()
            comment.like_num = max(0, comment.like_num - 1)
            comment.save(update_fields=["like_num"])
            logger.info(f'商品评论 取消点赞成功：用户={user.username}, 评论ID={good_comment_id}')
            return common_response(status=status.HTTP_200_OK, message="取消点赞成功",
                                   data={"is_liked": False, "like_num": comment.like_num})
        else:
            CommentLike.objects.create(user=user, comment=comment)
            comment.like_num += 1
            comment.save(update_fields=["like_num"])
            logger.info(f'商品评论 点赞成功：用户={user.username}, 评论ID={good_comment_id}')
            return common_response(status=status.HTTP_200_OK, message="点赞成功",
                                   data={"is_liked": True, "like_num": comment.like_num})
