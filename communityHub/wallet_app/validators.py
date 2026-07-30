import uuid
from datetime import datetime


def create_recharge_number():
    """ 生成充值订单的唯一编号 """
    uuid_str = str(uuid.uuid4().hex[:8])
    create_time = datetime.now().strftime('%Y%m%d%H%M%S%f')
    return f"RE_{create_time}__{uuid_str}"
