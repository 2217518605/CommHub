from django.db import models
from django.core.validators import RegexValidator

from models.base import BaseModel


class Organization(BaseModel):
    """ 社区组织模型 """
    org_name = models.CharField(max_length=50, help_text="社区组织名称", verbose_name="社区组织名称",
                                null=False, blank=False, unique=True, db_column="name")
    contact_person = models.CharField(max_length=20, help_text="组织联系人", verbose_name="组织联系人", null=False,
                                      blank=False, )
    contact_phone = models.CharField(max_length=11, help_text="组织联系电话", verbose_name="组织联系电话", null=False,
                                     blank=False, validators=[RegexValidator(regex=r"^1[3-9]\d{9}$",
                                                                             message="请输入有效的手机号码（11位数字，以13-19开头)",
                                                                             code='invalid_phone')])
    contact_email = models.EmailField(verbose_name="社区联系邮箱", help_text="社区联系邮箱", null=True, blank=True)
    address = models.CharField('地址', max_length=100, null=True, blank=True)
    description = models.TextField(help_text="社区组织描述", verbose_name="社区组织描述", null=True, blank=True)
    org_avatar = models.ImageField(upload_to="org_avatars/", default="org_avatars/default_org_avatar.png",
                                   help_text="组织头像",
                                   verbose_name="组织头像", null=True, blank=True)

    class Meta:
        db_table = "t_organization"
        verbose_name = "社区组织"
        verbose_name_plural = verbose_name