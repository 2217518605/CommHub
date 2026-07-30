import base64
import json
import logging
import os
import time
import traceback
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePrecreateModel import AlipayTradePrecreateModel
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.request.AlipayTradePrecreateRequest import AlipayTradePrecreateRequest
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class AlipayPaymentResult:
    order_number: str
    pay_url: str
    out_trade_no: str
    total_amount: str


def _read_key(path: str) -> str:
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return path


class AlipayClient:
    """ 支付宝沙盒支付客户端 """

    def __init__(self):
        alipay_client_config = AlipayClientConfig()
        alipay_client_config.server_url = settings.ALIPAY_GATEWAY
        alipay_client_config.app_id = settings.ALIPAY_APP_ID
        alipay_client_config.app_private_key = _read_key(settings.ALIPAY_PRIVATE_KEY)
        alipay_client_config.alipay_public_key = _read_key(settings.ALIPAY_ALIPAY_PUBLIC_KEY)
        self.sdk_client = DefaultAlipayClient(alipay_client_config, logger)

    def build_payment_url(self, *, order_number: str, total_amount: Decimal, subject: str, body: str = "") -> AlipayPaymentResult:
        return self.build_qr_payment_url(
            order_number=order_number, total_amount=total_amount,
            subject=subject, body=body
        )

    def build_qr_payment_url(self, *, order_number: str, total_amount: Decimal, subject: str, body: str = "") -> AlipayPaymentResult:
        """使用 alipay.trade.precreate 生成当面付二维码

        直接预下单生成二维码，扫码者登录自己的支付宝账号完成支付。
        """

        precreate_model = AlipayTradePrecreateModel()
        precreate_model.out_trade_no = order_number
        precreate_model.total_amount = str(total_amount)
        precreate_model.subject = subject

        precreate_request = AlipayTradePrecreateRequest(biz_model=precreate_model)
        precreate_request.notify_url = settings.ALIPAY_NOTIFY_URL or ""

        last_error = None
        for attempt in range(3):
            try:
                response = self.sdk_client.execute(precreate_request)
                if isinstance(response, str):
                    response = json.loads(response)

                qr_code = response.get("qr_code", "")
                if qr_code:
                    logger.info(f"支付宝预下单成功: {order_number}")
                    return AlipayPaymentResult(
                        order_number=order_number,
                        pay_url=qr_code,
                        out_trade_no=order_number,
                        total_amount=str(total_amount),
                    )

                if response.get("code") != "10000":
                    raise RuntimeError(f"预下单失败: {response}")

            except Exception as exc:
                last_error = exc
                msg = str(exc)
                if "504" in msg or "timed out" in msg.lower():
                    logger.warning(f"支付宝预下单 504/超时，第{attempt+1}次重试: {order_number}")
                    time.sleep(2)
                    continue
                raise

        logger.error(f"生成支付宝二维码失败(重试3次): {order_number}")
        logger.error(traceback.format_exc())
        raise last_error

    def build_page_payment_html(self, *, order_number: str, total_amount: Decimal, subject: str, body: str = "") -> str:
        """使用 alipay.trade.page.pay 生成 PC 网页支付 HTML，直接在浏览器打开即可支付 """

        model = AlipayTradePagePayModel()
        model.out_trade_no = order_number
        model.total_amount = str(total_amount)
        model.subject = subject
        model.body = body or subject
        model.product_code = "FAST_INSTANT_TRADE_PAY"

        request_obj = AlipayTradePagePayRequest(biz_model=model)
        request_obj.notify_url = settings.ALIPAY_NOTIFY_URL or ""
        request_obj.return_url = settings.ALIPAY_RETURN_URL or ""

        last_error = None
        for attempt in range(3):
            try:
                html = self.sdk_client.page_execute(request_obj)
                logger.info(f"支付宝网页支付生成成功: {order_number}")
                return html
            except Exception as exc:
                last_error = exc
                msg = str(exc)
                if "504" in msg or "timed out" in msg.lower():
                    logger.warning(f"支付宝网页支付 504/超时，第{attempt+1}次重试: {order_number}")
                    time.sleep(2)
                    continue
                raise

        logger.error(f"生成支付宝网页支付失败(重试3次): {order_number}")
        raise last_error

    def query_payment(self, order_number: str) -> dict:
        """查询支付宝订单支付状态 """

        model = AlipayTradeQueryModel()
        model.out_trade_no = order_number

        request_obj = AlipayTradeQueryRequest(biz_model=model)

        for attempt in range(5):
            try:
                response = self.sdk_client.execute(request_obj)
                if isinstance(response, str):
                    response = json.loads(response)
                logger.info(f"查询订单状态成功: {order_number} -> {response.get('trade_status', '?')}")
                return response
            except Exception as exc:
                msg = str(exc)
                if "504" in msg or "timed out" in msg.lower():
                    logger.warning(f"查询订单 504/超时，第{attempt+1}次重试: {order_number}")
                    time.sleep(3)
                    continue
                raise

        raise RuntimeError(f"查询订单状态失败(重试5次): {order_number}")

    def verify_notify(self, request_data: Dict[str, Any]) -> bool:
        signature = request_data.get("sign")
        if not signature:
            return False
        try:
            sign_content = "&".join(
                f"{k}={v}" for k in sorted(request_data.keys())
                if k not in ("sign", "sign_type") and v not in (None, "")
            )
            key_content = _read_key(settings.ALIPAY_ALIPAY_PUBLIC_KEY)
            public_key = serialization.load_pem_public_key(key_content.encode("utf-8"))
            public_key.verify(
                base64.b64decode(signature),
                sign_content.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as exc:
            logger.warning("支付宝验签失败: %s", exc)
            return False
