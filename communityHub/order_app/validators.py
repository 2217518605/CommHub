import uuid
from datetime import datetime
import time
import random


def create_order_number():
    """ 生成订单的唯一编号 """

    uuid_str = str(uuid.uuid4().hex[:8])
    create_time = datetime.now().strftime('%Y%m%d%H%M%S%f')

    return f"{create_time}__{uuid_str}"


def create_transaction_id():
    """ 生成第三方流水号(暂时模拟) """

    return str(uuid.uuid4().hex[:16])


def create_courier_number():
    """ 创建快递单号 """

    time_str = int(time.time())
    random_code = random.randint(100000, 999999)

    return f"EXP__{time_str}__{random_code}"
