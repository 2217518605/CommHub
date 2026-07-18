import base64
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict
from urllib.parse import quote_plus, urlencode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class AlipayPaymentResult:
    order_number: str
    pay_url: str
    out_trade_no: str
    total_amount: str


class AlipayClient:
    """ 支付宝沙盒支付客户端，负责生成支付链接与验签 """

    def __init__(self):
        """ 初始化支付宝客户端配置 """

        self.app_id = settings.ALIPAY_APP_ID
        self.private_key = settings.ALIPAY_PRIVATE_KEY
        self.alipay_public_key = settings.ALIPAY_ALIPAY_PUBLIC_KEY
        self.gateway = settings.ALIPAY_GATEWAY
        self.sign_type = settings.ALIPAY_SIGN_TYPE
        self.charset = settings.ALIPAY_CHARSET
        self.timeout = settings.ALIPAY_TIMEOUT

    def _load_private_key(self):
        """ 加载支付宝应用私钥 """

        if not self.private_key:
            raise ValueError("支付宝私钥未配置")
        return serialization.load_pem_private_key(self.private_key.encode(self.charset), password=None)

    def _load_public_key(self):
        """ 加载支付宝公钥 """

        if not self.alipay_public_key:
            raise ValueError("支付宝公钥未配置")
        return serialization.load_pem_public_key(self.alipay_public_key.encode(self.charset))

    def _build_sign_content(self, params: Dict[str, Any]) -> str:
        """ 拼接待签名参数串 """

        items = []
        for key in sorted(params.keys()):
            value = params[key]
            if value in (None, ""):
                continue
            items.append(f"{key}={value}")
        return "&".join(items)

    def _sign(self, params: Dict[str, Any]) -> str:
        """ 对请求参数进行 RSA2 签名 """

        sign_content = self._build_sign_content(params)
        private_key = self._load_private_key()
        signature = private_key.sign(
            sign_content.encode(self.charset),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode(self.charset)

    def verify(self, params: Dict[str, Any], signature: str) -> bool:
        """ 验签支付宝返回参数 """

        try:
            content = self._build_sign_content(params)
            public_key = self._load_public_key()
            public_key.verify(
                base64.b64decode(signature),
                content.encode(self.charset),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as exc:
            logger.warning("支付宝验签失败: %s", exc, exc_info=True)
            return False

    def build_payment_url(self, *, order_number: str, total_amount: Decimal, subject: str, body: str = "") -> AlipayPaymentResult:
        """ 生成支付宝网页支付链接 """

        if not self.app_id:
            raise ValueError("支付宝APP_ID未配置")
        biz_content = {
            "out_trade_no": order_number,
            "total_amount": f"{Decimal(total_amount):.2f}",
            "subject": subject,
            "product_code": "FAST_INSTANT_TRADE_PAY",
            "body": body,
        }
        params = OrderedDict(
            [
                ("app_id", self.app_id),
                ("method", "alipay.trade.page.pay"),
                ("format", "JSON"),
                ("charset", self.charset),
                ("sign_type", self.sign_type),
                ("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                ("version", "1.0"),
                ("notify_url", settings.ALIPAY_NOTIFY_URL),
                ("return_url", settings.ALIPAY_RETURN_URL),
                ("biz_content", json.dumps(biz_content, ensure_ascii=False, separators=(",", ":"))),
            ]
        )
        sign = self._sign(params)
        params["sign"] = sign
        query = urlencode(params, quote_via=quote_plus)
        return AlipayPaymentResult(
            order_number=order_number,
            pay_url=f"{self.gateway}?{query}",
            out_trade_no=order_number,
            total_amount=f"{Decimal(total_amount):.2f}",
        )

    def verify_notify(self, request_data: Dict[str, Any]) -> bool:
        """ 验签支付宝异步通知请求 """

        signature = request_data.get("sign")
        if not signature:
            return False
        params = {k: v for k, v in request_data.items() if k != "sign"}
        return self.verify(params, signature)
