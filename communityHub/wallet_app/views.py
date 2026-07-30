import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action

from config.alipay import AlipayClient
from config.authentication import IsCommonUser
from config.decorators.common import api_delete, api_doc, api_get, api_post
from config.help_tools import CommonPageNumberPagination, common_response, get_client_ip, get_object_or_404
from wallet_app.models import Wallet, RechargeOrder, BalanceLog
from wallet_app.serializers import (
    RechargeCreateSerializer, RechargeResponseSerializer, RechargePaymentSerializer,
    WalletResponseSerializer, BalanceLogSerializer
)
from wallet_app.validators import create_recharge_number

logger = logging.getLogger(__name__)


class WalletViewSet(ViewSet):
    """ 钱包相关视图集 """
    permission_classes = [IsCommonUser]

    @api_doc(tags=["钱包 获取我的钱包信息"], response_body=WalletResponseSerializer)
    @api_get
    def get_wallet(self, request):
        """ 获取当前用户的钱包信息 """
        user = request.user

        wallet, created = Wallet.objects.get_or_create(user=user)

        return common_response(
            status=status.HTTP_200_OK,
            message="获取钱包信息成功",
            data=WalletResponseSerializer(wallet).data
        )

    @api_doc(tags=["钱包 获取余额变动记录"], response_body=BalanceLogSerializer)
    @api_get
    def list_balance_logs(self, request):
        """ 获取当前用户的余额变动记录（分页） """
        user = request.user

        queryset = BalanceLog.objects.filter(user=user, is_deleted=False).order_by('-create_time')

        paginator = CommonPageNumberPagination()
        paginated_data = paginator.paginate_queryset(queryset, request)
        serializer = BalanceLogSerializer(paginated_data, many=True)

        return paginator.get_paginated_response(serializer.data)

    @api_doc(tags=["钱包 删除余额变动记录"], request_body=None, response_body=None)
    @api_delete
    def destroy_balance_log(self, request, log_id):
        """ 删除单条余额变动记录 """
        user = request.user

        log = get_object_or_404(BalanceLog, msg="余额变动记录不存在", id=log_id)

        if log.user_id != user.id:
            return common_response(
                status=status.HTTP_403_FORBIDDEN,
                message="无权删除该记录"
            )

        log.is_deleted = True
        log.save(update_fields=['is_deleted', 'update_time'])
        logger.info(f"钱包 删除余额变动记录，用户：{user.username}，记录ID：{log_id}")

        return common_response(
            status=status.HTTP_200_OK,
            message="删除成功"
        )

    @api_doc(tags=["钱包 批量删除余额变动记录"], request_body=None, response_body=None)
    @api_post
    def bulk_destroy_balance_logs(self, request):
        """ 批量删除余额变动记录 """
        user = request.user
        ids = request.data.get("ids", [])

        if not isinstance(ids, list):
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message="参数 ids 必须为列表"
            )

        if len(ids) == 0:
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message="请选择要删除的记录"
            )

        if len(ids) > 100:
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message="单次最多删除 100 条记录"
            )

        deleted_count, _ = BalanceLog.objects.filter(
            id__in=ids, user=user, is_deleted=False
        ).update(is_deleted=True)

        logger.info(f"钱包 批量删除余额变动记录，用户：{user.username}，删除数量：{deleted_count}")

        return common_response(
            status=status.HTTP_200_OK,
            message=f"成功删除 {deleted_count} 条记录",
            data={"deleted": deleted_count}
        )

    @api_doc(tags=["钱包 清空所有余额变动记录"], request_body=None, response_body=None)
    @api_delete
    def clear_balance_logs(self, request):
        """ 清空当前用户所有余额变动记录 """
        user = request.user

        deleted_count = BalanceLog.objects.filter(user=user, is_deleted=False).update(is_deleted=True)

        logger.info(f"钱包 清空余额变动记录，用户：{user.username}，删除数量：{deleted_count}")

        return common_response(
            status=status.HTTP_200_OK,
            message=f"成功清空 {deleted_count} 条记录",
            data={"deleted": deleted_count}
        )


class RechargeViewSet(ViewSet):
    """ 充值相关视图集 """
    permission_classes = [IsCommonUser]

    @api_doc(tags=["充值 创建充值订单"], request_body=RechargeCreateSerializer, response_body=RechargeResponseSerializer)
    @api_post
    @method_decorator(ratelimit(key="user", rate="10/m", block=True, method="POST"))
    def create(self, request):
        """ 创建充值订单 """
        user = request.user

        serializer = RechargeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"充值 创建充值订单参数校验失败：{serializer.errors}")
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message="参数校验失败",
                data=serializer.errors
            )

        amount = serializer.validated_data['amount']

        try:
            with transaction.atomic():
                recharge_order =RechargeOrder.objects.create(
                    user=user,
                    recharge_number=create_recharge_number(),
                    amount=amount,
                    status=RechargeOrder.Status.PENDING
                )

                logger.info(f"充值 创建充值订单成功，用户：{user.username}，订单号：{recharge_order.recharge_number}，金额：{amount}")
                return common_response(
                    status=status.HTTP_201_CREATED,
                    message="创建充值订单成功",
                    data=RechargeResponseSerializer(recharge_order).data
                )
        except Exception as e:
            logger.error(f"充值 创建充值订单失败：{e}", exc_info=True)
            return common_response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="创建充值订单失败"
            )

    @api_doc(tags=["充值 获取充值订单列表"], response_body=RechargeResponseSerializer)
    @api_get
    def list(self, request):
        """ 获取当前用户的充值订单列表（分页） """
        user = request.user

        queryset = RechargeOrder.objects.filter(user=user).order_by('-create_time')

        paginator = CommonPageNumberPagination()
        paginated_data = paginator.paginate_queryset(queryset, request)
        serializer = RechargeResponseSerializer(paginated_data, many=True)

        return paginator.get_paginated_response(serializer.data)

    @api_doc(tags=["充值 获取单个充值订单"], response_body=RechargeResponseSerializer)
    @api_get
    def retrieve(self, request, recharge_number):
        """ 获取单个充值订单详情 """
        user = request.user

        recharge_order = get_object_or_404(
            RechargeOrder,
            msg="充值订单不存在",
            recharge_number=recharge_number
        )

        if recharge_order.user_id != user.id:
            return common_response(
                status=status.HTTP_403_FORBIDDEN,
                message="无权查看该充值订单"
            )

        return common_response(
            status=status.HTTP_200_OK,
            message="获取充值订单成功",
            data=RechargeResponseSerializer(recharge_order).data
        )

    @api_doc(tags=["充值 删除充值订单"], request_body=None, response_body=None)
    @api_delete
    def destroy(self, request, recharge_number):
        """ 删除指定充值订单 """
        user = request.user

        recharge_order = get_object_or_404(
            RechargeOrder,
            msg="充值订单不存在",
            recharge_number=recharge_number
        )

        if recharge_order.user_id != user.id:
            return common_response(
                status=status.HTTP_403_FORBIDDEN,
                message="无权删除该充值订单"
            )

        recharge_order.delete()
        logger.info(f"充值 删除订单，用户：{user.username}，订单号：{recharge_number}")

        return common_response(
            status=status.HTTP_200_OK,
            message="删除充值订单成功"
        )

    @api_doc(tags=["充值 批量删除充值订单"], request_body=None, response_body=None)
    @api_post
    def bulk_destroy(self, request):
        """ 批量删除充值订单 """
        user = request.user
        ids = request.data.get("ids", [])

        if not isinstance(ids, list):
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message="参数 ids 必须为列表"
            )

        if len(ids) == 0:
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message="请选择要删除的订单"
            )

        if len(ids) > 100:
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message="单次最多删除 100 条记录"
            )

        deleted_count, _ = RechargeOrder.objects.filter(
            id__in=ids, user=user
        ).delete()

        logger.info(f"充值 批量删除，用户：{user.username}，删除数量：{deleted_count}")

        return common_response(
            status=status.HTTP_200_OK,
            message=f"成功删除 {deleted_count} 条充值订单",
            data={"deleted": deleted_count}
        )


class RechargePaymentViewSet(ViewSet):
    """ 充值支付视图集 """
    permission_classes = [IsCommonUser]

    @api_doc(tags=["充值支付 生成支付宝支付链接"], request_body=None, response_body=RechargePaymentSerializer)
    @api_post
    @method_decorator(ratelimit(key="user", rate="10/m", block=True, method="POST"))
    def create(self, request):
        """ 生成支付宝支付链接 """
        user = request.user
        recharge_number = request.data.get("recharge_number")

        recharge_order = get_object_or_404(
            RechargeOrder.objects.select_related("user"),
            msg="充值订单不存在",
            recharge_number=recharge_number
        )

        if recharge_order.user_id != user.id:
            return common_response(
                status=status.HTTP_403_FORBIDDEN,
                message="无权操作该充值订单"
            )

        if recharge_order.status != RechargeOrder.Status.PENDING:
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message=f"充值订单状态不允许支付（当前状态：{recharge_order.get_status_display()}）"
            )

        client = AlipayClient()
        try:
            payment = client.build_qr_payment_url(
                order_number=recharge_order.recharge_number,
                total_amount=recharge_order.amount,
                subject=f"钱包充值-{recharge_order.amount}元",
                body=f"充值订单-{recharge_order.recharge_number}"
            )

            logger.info(f"充值支付 生成支付链接成功，订单号：{recharge_number}")
            return common_response(
                status=status.HTTP_200_OK,
                message="生成支付链接成功",
                data={
                    "recharge_number": payment.order_number,
                    "pay_url": payment.pay_url,
                    "out_trade_no": payment.out_trade_no,
                    "total_amount": payment.total_amount,
                }
            )
        except Exception as exc:
            logger.error(f"充值支付 生成支付链接失败：{exc}", exc_info=True)
            return common_response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="生成支付链接失败"
            )

    @api_doc(tags=["充值支付 生成支付宝网页支付"], request_body=None, response_body=None)
    @api_post
    @method_decorator(ratelimit(key="user", rate="10/m", block=True, method="POST"))
    def page_pay(self, request):
        """ 生成支付宝网页支付 HTML """
        user = request.user
        recharge_number = request.data.get("recharge_number")

        recharge_order = get_object_or_404(
            RechargeOrder,
            msg="充值订单不存在",
            recharge_number=recharge_number
        )

        if recharge_order.user_id != user.id:
            return common_response(
                status=status.HTTP_403_FORBIDDEN,
                message="无权操作该充值订单"
            )

        if recharge_order.status != RechargeOrder.Status.PENDING:
            return common_response(
                status=status.HTTP_400_BAD_REQUEST,
                message=f"充值订单状态不允许支付（当前状态：{recharge_order.get_status_display()}）"
            )

        from django.http import HttpResponse
        client = AlipayClient()
        try:
            html = client.build_page_payment_html(
                order_number=recharge_order.recharge_number,
                total_amount=recharge_order.amount,
                subject=f"钱包充值-{recharge_order.amount}元",
                body=f"充值订单-{recharge_order.recharge_number}"
            )
            return HttpResponse(html)
        except Exception as exc:
            logger.error(f"充值支付 生成网页支付失败：{exc}", exc_info=True)
            return common_response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="生成网页支付失败"
            )

    @api_doc(tags=["充值支付 查询支付状态"], request_body=None, response_body=None)
    @api_post
    @transaction.atomic
    def check_pay(self, request):
        """ 主动查询支付宝支付状态并更新充值订单 """
        user = request.user
        recharge_number = request.data.get("recharge_number")

        recharge_order = get_object_or_404(
            RechargeOrder.objects.select_for_update(), # 使用select_for_update()来防止并发问题
            msg="充值订单不存在",
            recharge_number=recharge_number
        )

        if recharge_order.user_id != user.id:
            return common_response(
                status=status.HTTP_403_FORBIDDEN,
                message="无权操作该充值订单"
            )

        if recharge_order.status == RechargeOrder.Status.PAID:
            return common_response(
                status=status.HTTP_200_OK,
                message="充值已完成",
                data={
                    "recharge_number": recharge_order.recharge_number,
                    "status": recharge_order.status,
                    "is_paid": True,
                }
            )

        client = AlipayClient()
        try:
            result = client.query_payment(recharge_order.recharge_number)
        except Exception as exc:
            logger.warning(f"充值支付 查询支付状态失败（可重试）：{exc}")
            return common_response(
                status=status.HTTP_200_OK,
                message="查询支付状态超时，请稍后重试",
                data={
                    "recharge_number": recharge_order.recharge_number,
                    "status": recharge_order.status,
                    "is_paid": False,
                    "retry": True,
                }
            )

        trade_status = result.get("trade_status", "")

        if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            return self._process_payment_success(recharge_order, result, request)
        elif trade_status == "TRADE_CLOSED":
            recharge_order.status = RechargeOrder.Status.EXPIRED
            recharge_order.save(update_fields=["status", "update_time"])
            return common_response(
                status=status.HTTP_200_OK,
                message="充值订单已过期",
                data={
                    "recharge_number": recharge_order.recharge_number,
                    "status": recharge_order.status,
                    "is_paid": False,
                }
            )

        return common_response(
            status=status.HTTP_200_OK,
            message="充值尚未完成，请继续等待",
            data={
                "recharge_number": recharge_order.recharge_number,
                "status": recharge_order.status,
                "is_paid": False,
            }
        )

    def _process_payment_success(self, recharge_order, alipay_result, request):
        """ 处理充值成功逻辑 """
        trade_no = alipay_result.get("trade_no", "")
        total_amount = alipay_result.get("total_amount", str(recharge_order.amount))

        try:
            with transaction.atomic():
                recharge_order.status = RechargeOrder.Status.PAID
                recharge_order.pay_time = timezone.now()
                recharge_order.save(update_fields=["status", "pay_time", "update_time"])

                user = recharge_order.user
                balance_before = user.balance

                amount = Decimal(total_amount)
                user.balance = F('balance') + amount
                user.save(update_fields=['balance', 'update_time'])

                user.refresh_from_db()
                balance_after = user.balance

                BalanceLog.objects.create(
                    user=user,
                    change_amount=amount,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    source_type=BalanceLog.SourceType.RECHARGE,
                    source_id=recharge_order.id,
                    remark=f"充值成功，支付宝流水号：{trade_no}"
                )

                logger.info(
                    f"充值支付 充值成功，用户：{user.username}，订单号：{recharge_order.recharge_number}，"
                    f"金额：{total_amount}，流水号：{trade_no}"
                )

                return common_response(
                    status=status.HTTP_200_OK,
                    message="充值成功",
                    data={
                        "recharge_number": recharge_order.recharge_number,
                        "status": recharge_order.status,
                        "is_paid": True,
                        "amount": total_amount,
                    }
                )
        except Exception as e:
            logger.error(f"充值支付 处理充值成功逻辑失败：{e}", exc_info=True)
            return common_response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="处理充值结果失败"
            )


class AlipayRechargeNotifyViewSet(ViewSet):
    """ 充值支付宝异步回调视图集 """
    authentication_classes = []
    permission_classes = []

    @api_doc(tags=["充值回调 处理支付宝异步通知"], request_body=None, response_body=None)
    def post(self, request):
        """ 处理支付宝异步回调 """
        from django.http import HttpResponse

        client = AlipayClient()
        payload = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)

        if not client.verify_notify(payload):
            logger.warning(f"充值回调 验签失败：{payload}")
            return HttpResponse("failure", status=400)

        trade_status = payload.get("trade_status")
        out_trade_no = payload.get("out_trade_no")
        trade_no = payload.get("trade_no")
        total_amount = payload.get("total_amount")

        logger.info(f"充值回调 收到回调，订单号：{out_trade_no}，状态：{trade_status}，金额：{total_amount}")

        if trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
            return HttpResponse("success")

        try:
            with transaction.atomic():
                recharge_order = RechargeOrder.objects.select_for_update().get(
                    recharge_number=out_trade_no
                )

                if recharge_order.status == RechargeOrder.Status.PAID:
                    logger.info(f"充值回调 订单已处理，跳过：{out_trade_no}")
                    return HttpResponse("success")

                if Decimal(str(total_amount)) != recharge_order.amount:
                    logger.warning(
                        f"充值回调 金额不匹配，订单：{recharge_order.amount}，回调：{total_amount}"
                    )
                    recharge_order.status = RechargeOrder.Status.FAILED
                    recharge_order.save(update_fields=["status", "update_time"])
                    return HttpResponse("success")

                user = recharge_order.user
                balance_before = user.balance

                amount = Decimal(str(total_amount))
                user.balance = F('balance') + amount
                user.save(update_fields=['balance', 'update_time'])

                user.refresh_from_db()
                balance_after = user.balance

                recharge_order.status = RechargeOrder.Status.PAID
                recharge_order.pay_time = timezone.now()
                recharge_order.save(update_fields=["status", "pay_time", "update_time"])

                BalanceLog.objects.create(
                    user=user,
                    change_amount=amount,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    source_type=BalanceLog.SourceType.RECHARGE,
                    source_id=recharge_order.id,
                    remark=f"充值成功（回调），支付宝流水号：{trade_no}"
                )

                logger.info(
                    f"充值回调 充值成功处理完成，用户：{user.username}，订单号：{out_trade_no}，金额：{total_amount}"
                )
        except RechargeOrder.DoesNotExist:
            logger.warning(f"充值回调 充值订单不存在：{out_trade_no}")
        except Exception as e:
            logger.error(f"充值回调 处理失败：{e}", exc_info=True)
            return HttpResponse("failure", status=500)

        return HttpResponse("success")

    @api_doc(tags=["充值回调 支付宝同步跳转"], request_body=None, response_body=None)
    def get(self, request):
        """ 处理支付宝同步跳转 """
        return self.post(request)
