# CommHub

#### 介绍
这是 "邻里汇" 平台的后台代码，”邻里汇“平台，集成社区管理、购物、评论、组织等等模块于一起的一个平台。
主要功能是：用户中心、设备模块、购物车模块、用餐模块、报表中心、订单模块、会员模块、优惠卷模块、商城模块、社区模块。组织模块

#### 软件架构
本项目基于 Django 框架进行开发，搭配mysql数据库、redis数据库、mongodb数据库，celery框架进行开发。


#### 安装以及启动方法
1、创建虚拟环境 conda create --name commhub_v1_env python=3.11.9

2、激活虚拟环境 conda activate commhub_v1_env

3、下载依赖包：
$ pip install -r requirements.txt -i https://pypi.douban.com/simple/
$ pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
$ pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

4、迁移数据库：python manage.py makemigrations

5、执行迁移 python manage.py migrate

6、日志目录：mkdir -p logs

7、启动 redis 服务：redis-server reids-cli

8、启动服务 python manage.py runserver


#### 导出 swagger 文档
1、安装 swagger-ui-bundle：pip install swagger-ui-bundle

2、生成 swagger 文档 python manage.py generateschemas

### 查看 swagger 文档 
$ http://127.0.0.1:8000/swagger/

### 导出 requirements.txt
$ pip freeze > requirements.txt

