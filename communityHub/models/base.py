from django.db import models

class BaseModel(models.Model):
    _version = models.FloatField('内置版本号',default=1.0,null=False)

    create_time = models.DateTimeField('创建时间', blank=True, null=False, auto_now_add=True)
    update_time = models.DateTimeField('更新时间', blank=True, null=False, auto_now=True)
    
    class Meta:
        abstract = True # 抽象，不会为该类创建实际的数据表，仅作为其他模型的继承模板

