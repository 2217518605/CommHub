import logging
import time
import datetime

from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
# from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework.permissions import IsAuthenticated, AllowAny

from user_app.models import User, UserLoginLog
from config.decorators.common import api_doc, api_get, api_post, api_put, api_delete, require_login
from config.help_tools import CommonPageNumberPagination
from user_app.serializers import UserRegisterSerializer, UserResponseSerializer, UserLoginSerializer, \
    UserUpdateSerializer, UserDeleteSerializer, UserQueryByNameSerializer
from config.serializers.base import EmptySerializer
from organization_app.models import Organization
from config.help_tools import get_client_ip, common_response
from user_app.validators import check_ip_lock, check_account_lock, record_login_failure, clear_login_success_cache, \
    record_ip_register
from config.authentication import IsAdmin, IsSuperAdmin, IsPublic, IsCommonUser
from config.help_tools import get_object_or_404

logger = logging.getLogger(__name__)


class UserRetrieveView(ViewSet):
    permission_classes = [IsCommonUser]

    def get_permissions(self):
        """ 注册放开权限，其余需要登录 """
        if self.action == "create":
            return [IsPublic()]
        return [permission() for permission in self.permission_classes]

    @api_doc(tags=["用户 用户注册"], request_body=UserRegisterSerializer, response_body=UserResponseSerializer)
    @api_post
    @transaction.atomic
    def create(self, request):

        # 限制一个 IP 重复注册(10次)
        ip_lock_response = check_ip_lock(request)
        if ip_lock_response:
            return ip_lock_response

        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            register_data = serializer.save()
            account = serializer.validated_data['account']
            logger.info(f"用户 用户创建成功: account={account}")
            record_ip_register(request)  # 记录 IP 注册次数
            return common_response(status=status.HTTP_200_OK, message="用户 创建用户成功",
                                   data=UserResponseSerializer(register_data).data)
        else:
            logger.error(f'用户 创建用户错误：{serializer.errors}', exc_info=True)
            record_ip_register(request)  # 记录 IP 注册次数
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="用户 创建用户失败",
                                   data=serializer.errors)

    @api_doc(tags=["用户 单个用户查询"], response_body=UserResponseSerializer)
    @api_get
    def retrieve(self, request, pk):

        # 防止越权查看
        if int(pk) != request.user.pk:
            logger.warning(f"用户 发生越权查询，用户查询失败:用户 ID ：{pk} 的用户非法")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户 非法查询")

        user = get_object_or_404(User, msg="用户不存在", pk=pk)
        return common_response(status=status.HTTP_200_OK, message="用户 查询成功",
                               data=UserResponseSerializer(user).data)

    @api_doc(tags=["用户 用户更新"], request_body=UserUpdateSerializer, response_body=UserResponseSerializer)
    @api_put
    def update(self, request, pk):

        logger.info(f"用户 用户更新:要求更新的用户 ID ：{pk}")

        # 防止不是本人的恶意修改
        if request.user.pk != int(pk):
            logger.warning(f"用户 发生越权修改，用户更新失败:用户 ID ：{pk} 的用户非法")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户 非法更新")

        try:
            user = User.objects.select_related("organization").get(pk=pk)

            serializer = UserUpdateSerializer(instance=user, data=request.data)
            if serializer.is_valid():
                update_data = serializer.save()
                logger.info(
                    f"用户 用户更新成功: account={update_data.account}")
                return common_response(status=status.HTTP_200_OK, message=f"用户 {update_data.account} 更新成功",
                                       data=UserResponseSerializer(update_data).data)
            else:
                logger.error(f'用户 用户更新错误：{serializer.errors}', exc_info=True)
                return common_response(status=status.HTTP_400_BAD_REQUEST, message="用户 更新失败",
                                       data=serializer.errors)

        except User.DoesNotExist:
            logger.warning(f"用户 用户更新失败:用户 ID ：{pk} 不存在")
            return common_response(status=status.HTTP_404_NOT_FOUND, message="用户 不存在")

    @api_doc(tags=["用户 用户删除"], request_body=UserDeleteSerializer, response_body=EmptySerializer)
    @api_delete
    def destroy(self, request, pk):

        logger.info(f"用户 用户删除:要求删除的用户 ID ：{pk}")

        if request.user.pk != int(pk):
            logger.warning(f"用户 发生越权删除，用户删除失败:用户 ID ：{pk} 的用户非法")
            return common_response(status=status.HTTP_403_FORBIDDEN, message="用户 删除失败，您无权删除该用户")

        try:
            user = User.objects.select_related("organization").get(pk=pk)
            user_name = user.username
            user_account = user.account
            user.delete()
            logger.info(f"用户 用户删除成功: username={user_name} account={user_account}")
            return common_response(status=status.HTTP_200_OK, message="用户 删除成功")
        except User.DoesNotExist:
            logger.warning(f"用户 用户删除失败:用户 ID ：{pk} 不存在")
            return common_response(status=status.HTTP_404_NOT_FOUND, message="用户 不存在")


class UserLoginView(ViewSet):
    permission_classes = [IsCommonUser]

    def get_permissions(self):
        """ 放开登录的权限 """

        if self.action == "user_login":
            return [IsPublic()]
        return [permission() for permission in self.permission_classes]

    @api_doc(tags=["用户 用户登录"], request_body=UserLoginSerializer, response_body=UserResponseSerializer)
    @api_post
    def user_login(self, request):

        client_ip = get_client_ip(request)
        logger.info(f"用户检测到 IP: {client_ip} 进行了登录操作")

        ip_lock_response = check_ip_lock(request)
        if ip_lock_response:
            return ip_lock_response

        serializer = UserLoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"用户登录失败 - IP: {client_ip} 登录参数校验失败：{serializer.errors}")
            UserLoginLog.objects.create(user=request.user, login_time=timezone.now(), login_ip=get_client_ip(request),
                                        login_status="失败", login_type="登录失败")
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="用户 登录参数校验失败",
                                   data=serializer.errors)

        account = serializer.validated_data['account']
        password = serializer.validated_data['password']
        remember = serializer.validated_data['remember']

        logger.info(f"用户登录校验成功 IP: {client_ip} 账号：{account}")

        account_lock_response = check_account_lock(account)
        if account_lock_response:
            return account_lock_response

        try:
            with transaction.atomic():
                user = User.objects.select_related('organization').get(account=account)

                if not user.verify_password(password):
                    record_login_failure(request, account)
                    fail_count = cache.get(f"fail_account_{account}", 0)
                    logger.warning(f"用户 {account} 在 IP:{client_ip} 尝试登录，密码错误（第 {fail_count} 次）")
                    UserLoginLog.objects.create(user=user, login_time=timezone.now(), login_ip=get_client_ip(request),
                                                login_status="失败", login_type="登录失败")
                    return common_response(status=status.HTTP_401_UNAUTHORIZED, message="用户 登录密码错误")

                logger.info(f"用户 IP：{client_ip} 账号：{account} 登录成功，登录时间为：{user.last_login}")

                # 登录日志
                UserLoginLog.objects.create(user=user, login_time=timezone.now(), login_ip=get_client_ip(request),
                                            login_status="成功", login_type="正常登录")

                # 清楚失败的缓存
                clear_login_success_cache(account)

                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])

                access_token_lifetime = api_settings.ACCESS_TOKEN_LIFETIME
                refresh_token_lifetime = api_settings.REFRESH_TOKEN_LIFETIME
                if remember:
                    refresh_token_lifetime = datetime.timedelta(days=30)  # 30天有效期
                    access_token_lifetime = datetime.timedelta(days=1)  # 1天

                refresh = RefreshToken.for_user(user)
                refresh.set_exp(lifetime=refresh_token_lifetime)
                access = refresh.access_token
                access.set_exp(lifetime=access_token_lifetime)

                response_data = {
                    'user_info': UserResponseSerializer(user).data,
                    'token': {
                        'access_token': str(access),
                        'refresh_token': str(refresh),
                        'access_expire': int(access_token_lifetime.total_seconds()),
                        'refresh_expire': int(refresh_token_lifetime.total_seconds())
                    }
                }

            return common_response(status=status.HTTP_200_OK, message="用户 登录成功", data=response_data)

        except User.DoesNotExist:
            record_login_failure(request, account)
            logger.warning(f"用户账号 {account} 不存在")
            return common_response(status=status.HTTP_404_NOT_FOUND, message="用户 不存在")

    @api_doc(tags=["用户 用户登出"], request_body=EmptySerializer, response_body=EmptySerializer)
    @api_post
    def user_login_out(self, request):
        """ 核心就是处理refresh_token"""

        client_ip = get_client_ip(request)
        logger.debug(f'用户 本次用户登出请求的ip为: {client_ip}')
        raw_refresh_token = request.data.get('refresh_token')
        raw_access_token = request.data.get('access_token')
        if not raw_refresh_token:
            logger.warning(f'用户 refresh_token不能为空')
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="用户 refresh_token不能为空")

        if raw_access_token:
            try:
                token = AccessToken(raw_access_token)
                exp = token["exp"]  # 获取token的过期时间
                now_time = time.time()  # 获取当前时间戳
                remaining_seconds = exp - now_time  # 计算剩余秒数
                if remaining_seconds > 0:
                    logger.debug(f'Access token 加入黑名单，剩余有效期: {remaining_seconds}s')
                    cache.set(f"blacklist_access:{raw_access_token}", 1, timeout=remaining_seconds)
            except TokenError as e:
                logger.warning(f'用户 IP {client_ip}: 无效或过期的 access_token，跳过黑名单: {str(e)}')

        try:
            token = RefreshToken(raw_refresh_token)
            exp = token["exp"]
            now_time = time.time()
            remaining_seconds = exp - now_time

            if remaining_seconds > 0:
                cache.set(f'blacklist_refresh:{raw_refresh_token}', 1, timeout=remaining_seconds)
                logger.info(f'用户 IP {client_ip}: 用户登出成功，refresh_token 加入黑名单（剩余 {remaining_seconds}s）')

                # 记录登出日志：
                UserLoginLog.objects.create(user=request.user, login_time=timezone.now(),
                                            login_ip=get_client_ip(request), login_status="成功", login_type="正常登出")
            else:
                logger.info(f'用户 IP {client_ip}: refresh_token 已过期，无需加入黑名单')
                UserLoginLog.objects.create(user=request.user, login_time=timezone.now(),
                                            login_ip=get_client_ip(request),
                                            login_status="失败", login_type="登出失败")
            return common_response(status=status.HTTP_200_OK, message="用户 登出成功")

        except TokenError as e:
            logger.warning(f'用户 IP {client_ip}: refresh_token 无效或已过期: {str(e)}')
            UserLoginLog.objects.create(user=request.user, login_time=timezone.now(), login_ip=get_client_ip(request),
                                        login_status="失败", login_type="登出失败")
            return common_response(status=status.HTTP_401_UNAUTHORIZED, message="用户 登出失败")
        except Exception as e:
            logger.error(f'用户 IP {client_ip}: 登出发生未知错误: {str(e)}', exc_info=True)
            UserLoginLog.objects.create(user=request.user, login_time=timezone.now(), login_ip=get_client_ip(request),
                                        login_status="失败", login_type="登出失败")
            return common_response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, message="用户 登出失败")


class UserListView(ViewSet):
    pagination_class = CommonPageNumberPagination
    permission_classes = [IsCommonUser]

    @api_doc(tags=["用戶 通过关键词返回用户列表"], request_body=UserQueryByNameSerializer,
             response_body=UserResponseSerializer)
    @api_post
    def user_query_by_name(self, request):

        query_name = request.data.get("query_name") if "query_name" in request.data else None
        try:
            if query_name:
                user_list = User.objects.filter(username__icontains=query_name).select_related("organization").order_by(
                    '-create_time', '-id')
            else:
                user_list = User.objects.select_related("organization").all().order_by('-create_time', '-id')

            paginator = self.pagination_class()
            pagination_data = paginator.paginate_queryset(user_list, request)
            serializer = UserResponseSerializer(pagination_data, many=True)

            logger.info("用户列表查询成功")
            return paginator.get_paginated_response({
                "status": status.HTTP_200_OK,
                "message": "用户列表查询成功",
                "data": serializer.data
            })
        except Exception as e:
            logger.error("用户列表查询失败！", exc_info=True)
            return common_response(status=status.HTTP_400_BAD_REQUEST, message="用户列表查询失败")
