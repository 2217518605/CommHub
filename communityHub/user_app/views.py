import logging
import datetime
import time

from django.shortcuts import render
from django.db import transaction
from django.core.cache import cache
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.settings import api_settings

from user_app.models import User
from config.decorators.common import api_doc, api_get, api_post, api_put, api_delete
from config.help_tools import CommonPageNumberPagination
from user_app.serializers import UserRegisterSerializer, UserResponseSerializer, UserLoginSerializer
from config.serializers.base import EmptySerializer
from organization_app.models import Organization
from config.help_tools import get_client_ip
from user_app.validators import check_ip_lock, check_account_lock, record_login_failure, clear_login_success_cache

logger = logging.getLogger(__name__)


class UserRetrieveView(ViewSet):

    @api_doc(tags=["用户 用户注册"], request_body=UserRegisterSerializer, response_body=UserResponseSerializer)
    @api_post
    @transaction.atomic
    def create_user(self, request):

        serializer = UserRegisterSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            logger.info(f'用户 创建用户成功：用户信息：{serializer.data}')
            return Response({
                "status": status.HTTP_201_CREATED,
                "message": "创建用`户成功",
                "data": serializer.data
            })
        else:
            logger.error(f'用户 创建用户错误：{serializer.errors}')
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "创建用户失败",
                "data": serializer.errors
            })


class UserLoginView(ViewSet):

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
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "用户登录参数校验失败",
                "data": serializer.errors
            })

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

                if not user.check_password(password):
                    record_login_failure(request, account)
                    fail_count = cache.get(f"fail_account_{account}", 0)
                    logger.warning(f"用户 {account} 在 IP:{client_ip} 尝试登录，密码错误（第 {fail_count} 次）")
                    return Response({
                        "status": status.HTTP_401_UNAUTHORIZED,
                        "message": "密码错误",
                        "data": None
                    })

                logger.info(f"用户 IP：{client_ip} 账号：{account} 登录成功，登录时间为：{user.last_login}")
                clear_login_success_cache(account)

                user.last_login = datetime.datetime.now()
                user.save(update_fields=['last_login'])

                access_token_lifetime = api_settings.ACCESS_TOKEN_LIFETIME
                refresh_token_lifetime = api_settings.REFRESH_TOKEN_LIFETIME
                if remember:
                    refresh_token_lifetime = datetime.timedelta(days=30)  # 30天有效期

                refresh = RefreshToken.for_user(user)
                refresh.set_exp(refresh_token_lifetime)
                access = refresh.access_token
                access.set_exp(access_token_lifetime)

                response_data = {
                    'user_info': UserResponseSerializer(user).data,
                    'token': {
                        'access_token': str(access),
                        'refresh_token': str(refresh),
                        'access_expire': int(access.lifetime.total_seconds()),
                        'refresh_expire': int(refresh.lifetime.total_seconds())
                    }
                }

            return Response({
                "status": status.HTTP_200_OK,
                "message": "登录成功",
                "data": response_data
            })

        except User.DoesNotExist:
            record_login_failure(request, account)
            logger.warning(f"用户账号 {account} 不存在")
            return Response({
                "status": status.HTTP_404_NOT_FOUND,
                "message": "用户不存在",
                "data": None
            })

    @api_doc(tags=["用户 用户登出"], request_body=None, response_body=EmptySerializer)
    @api_post
    def user_login_out(self, request):
        """ 核心就是处理refresh_token"""

        client_ip = get_client_ip(request)
        logger.debug(f'用户 本次用户登出请求的ip为: {client_ip}')
        raw_refresh_token = request.data.get('refresh_token')
        raw_access_token = request.data.get('access_token')
        if not raw_refresh_token:
            logger.warning(f'用户 refresh_token不能为空')
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': 'refresh_token不能为空',
                'data': None
            })

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
                cache.set(f'blacklist_refresh:{token}', 1, timeout=remaining_seconds)
                logger.info(f'用户 IP {client_ip}: 用户登出成功，refresh_token 加入黑名单（剩余 {remaining_seconds}s）')
            else:
                logger.info(f'用户 IP {client_ip}: refresh_token 已过期，无需加入黑名单')

            return Response({
                'status': status.HTTP_200_OK,
                'message': '登出成功',
                'data': None
            }
            )

        except TokenError as e:
            logger.warning(f'用户 IP {client_ip}: refresh_token 无效或已过期: {str(e)}')
            return Response({
                'status': status.HTTP_400_BAD_REQUEST,
                'message': 'refresh_token 无效或已过期',
                'data': None
            })
        except Exception as e:
            logger.error(f'用户 IP {client_ip}: 登出发生未知错误: {str(e)}', exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '登出失败，请稍后重试',
                'data': None
            })
