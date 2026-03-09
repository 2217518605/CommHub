from django.db import models
from django.core.validators import RegexValidator
from django.contrib.auth.hashers import make_password

from models.base import BaseModel
from organization_app.models import Organization


class User(BaseModel):
    """ 用户模型 """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users',
                                     verbose_name='所属的社区组织', blank=True, null=True)
    username = models.CharField(max_length=20, verbose_name='用户名', help_text="用户名", blank=True,
                                null=True, default="默认用户")
    account = models.CharField(max_length=20, unique=True, verbose_name='账号', help_text="账号", blank=False,
                               null=False)
    password = models.CharField(max_length=256, verbose_name='密码', help_text="密码", blank=False, null=False)
    mobile = models.CharField(max_length=11, unique=True, verbose_name='手机号', help_text="手机号", blank=True,
                              null=True, validators=[RegexValidator(regex=r"^1[3-9]\d{9}$",
                                                                    message='请输入正确的手机号（11位）',
                                                                    code='invalid_mobile')])
    email = models.EmailField(max_length=50, unique=True, verbose_name='邮箱', help_text="邮箱", blank=True, null=True)
    avatar = models.ImageField(upload_to='user_avatars/',
                               default='user_avatars/default_user_avatar.png',
                               verbose_name='用户头像', help_text="用户头像", blank=True, null=True)
    birth_date = models.DateField(verbose_name='出生日', help_text="出生日", blank=True, null=True)
    id_card = models.CharField(max_length=18, unique=True, verbose_name='身份证号', help_text="身份证号", blank=True,
                               null=True, validators=[RegexValidator(
            regex=r"^[1-9]\d{5}(18|19|([23]\d))\d{2}((0[1-9])|(10|11|12))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx]$",
            message='请输入合适的身份证号（18位）',
            code='invalid_id_card')])
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='账户余额',
                                  help_text="账户余额")
    user_type = models.CharField(max_length=10,
                                 choices=[('resident', '居民'), ('admin', '社区管理员'), ('vendor', '商户')],
                                 default='resident', verbose_name='用户类型')
    is_active = models.BooleanField(default=True, verbose_name='是否激活', help_text='False=禁用/拉黑账号')
    is_staff = models.BooleanField(default=False, verbose_name='是否为管理员', help_text="是否为管理员")
    last_login = models.DateTimeField(blank=True, null=True, verbose_name='最后登录时间')

    def save(self, *args, **kwargs):
        """ 加密密码 """

        if self.password and not self.password.startswith(('pbkdf2_', 'argon2', 'bcrypt')):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account} ({self.get_user_type_display()})"

    class Meta:
        db_table = "t_user"
        verbose_name = "用户"
        verbose_name_plural = verbose_name


class UserLoginLog(BaseModel):
    """ 用户登录日志 """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_login_log", verbose_name="用户登录日志")
    login_time = models.DateTimeField(verbose_name='登录时间', help_text="登录时间", auto_now_add=True)
    login_ip = models.CharField(max_length=50, verbose_name="登录的ip", help_text="登录的ip")
    login_status = models.BooleanField(default=True, verbose_name='登录状态', help_text='True=成功，False=失败')
    login_type = models.CharField(max_length=10,
                                  choices=[('pc', '电脑端'), ('mobile', '移动端'), ('admin', '后台管理端')],
                                  default='mobile', verbose_name='登录端类型')

    class Meta:
        db_table = "t_user_login_log"
        verbose_name = "用户登录日志"
        verbose_name_plural = verbose_name


class UserAddress(BaseModel):
    """ 用户配送地址（用来实现简单的配送需求） """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_addresses", blank=False, null=False,
                             verbose_name="关联用户")
    name = models.CharField(max_length=20, verbose_name='收货人姓名', blank=False, null=False)
    mobile = models.CharField(max_length=11, verbose_name='手机号', blank=False, null=False,
                              validators=[RegexValidator(regex=r"^1[3-9]\d{9}$",
                                                         message='请输入正确的手机号（11位）',
                                                         code='invalid_mobile')])
    province = models.CharField(max_length=20, verbose_name='省', blank=False, null=False)
    city = models.CharField(max_length=20, verbose_name='市', blank=False, null=False)
    district = models.CharField(max_length=20, verbose_name='区', blank=False, null=False)
    address = models.CharField(max_length=200, verbose_name='详细地址', blank=True, null=True)
    building = models.CharField(max_length=50, verbose_name='楼栋', blank=True, null=True)
    unit = models.CharField(max_length=20, verbose_name='单元', blank=True, null=True)
    room = models.CharField(max_length=20, verbose_name='房号', blank=True, null=True)
    is_default = models.BooleanField(default=False, verbose_name='是否默认地址')

    class Meta:
        db_table = "t_user_address"
        verbose_name = "用户配送地址"
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(fields=['user', 'is_default'], condition=models.Q(is_default=True),
                                    name='unique_default_address')  # 一个用户只有一个默认地址
        ]
