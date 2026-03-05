import uuid
import random
import secrets
import string
import hashlib

from passlib.context import CryptContext


def generate_random_secret_sentry() -> str:
    """ 生成一个混合 UUID、随机字符串和数字的密钥 """

    uuid_part = str(uuid.uuid4()).replace('-', '')

    # 随机字符串 （大小写）
    characters = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(characters) for _ in range(32))

    # 混合两部分并且打乱顺序
    mixed_part = list(uuid_part + random_part)
    # random.shuffle(mixed_part)
    secrets.SystemRandom().shuffle(mixed_part)
    mixed_part = ''.join(mixed_part)
    return mixed_part


def md5_encrypt(encrypt_data: str) -> str:
    """ md5 加密一般数据 """

    return hashlib.md5(encrypt_data.encode('utf-8')).hexdigest()


data_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def encrypt_bcrypt(data: str) -> str:
    """ 更加安全的 bcrypt 加密"""

    return data_context.hash(data)


def decrypt_bcrypt(verify_data: str, hash_data: str) -> bool:
    """ 验证 bcrypt 加密数据 """

    return data_context.verify(verify_data, hash_data)
