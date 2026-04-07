import os

import django
from django.conf import settings
from celery import Celery
from celery.schedules import crontab

# 配置环境变量
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "communityHub.settings")
django.setup()

celery_app = Celery('communityHub_celery')

# 加载配置文件
celery_app.config_from_object("django.conf:settings", namespace='CELERY')

# 自动发现任务
celery_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# 配置定时任务
celery_app.conf.beat_schedule = {
    "clear-expire-coupon-every-day": {
        "task": "celery_tasks.clear_expire_coupon.clear_expire_coupon",
        "schedules": crontab(hour=3, minute=0),  # 每天凌晨3点执行
    }
}

celery_app.conf.timezone = 'Asia/Shanghai'