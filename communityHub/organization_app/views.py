import logging
import os
import datetime

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from openpyxl import workbook

from config.decorators.common import api_doc, api_get, api_post, api_put, api_delete
from config.serializers.base import EmptySerializer
from config.help_tools import CommonPageNumberPagination
from .serializers import OrganizationRequestSerializer, OrganizationResponseSerializer, OrganizationUpdateSerializer, \
    OrganizationDeleteSerializer
from .models import Organization

logger = logging.getLogger(__name__)


class OrganizationListView(ViewSet):
    pagination_class = CommonPageNumberPagination
    # application/vnd.openxmlformats-officedocument.spreadsheetml.sheet 是 .xlsx 格式 Excel 文件的标准 MIME 类型
    EXCEL_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    EXPORT_DIR_NAME = 'export_data'

    @api_doc(tag=["组织 获取组织列表"], response_body=OrganizationResponseSerializer)
    @api_post
    def list(self, request, is_export=False):
        try:
            org_list = Organization.objects.all().order_by('-id')
            logger.info(f'组织 获取组织列表成功，共获取 {org_list.count()} 条数据')
            paginator = self.pagination_class()
            pagination_data = paginator.paginate_queryset(org_list, request)
            if is_export:
                page = 0
                page_size = 100
                parent_file_path = os.path.join(os.path.dirname(__file__), self.EXPORT_DIR_NAME)
                os.makedirs(parent_file_path, exist_ok=True)  # 创建组织导出文件的存放目录，exist_ok 存在则不创建

                wb = workbook.Workbook()
                ws = wb.active
                headers = ["组织名称", "组织联系人", "组织联系电话", "组织联系邮箱", "组织地址", "组织描述", "组织头像"]
                ws.append(headers)

                # 海量数据的时候优化:
                while True:
                    fenye_data = org_list[page * page_size:(page + 1) * page_size]
                    if not fenye_data:
                        logger.info(f'组织 没有更多组织，已全部导出')
                        break
                    for detail_data in fenye_data:
                        row_data = [
                            detail_data.org_name,
                            detail_data.contact_person,
                            detail_data.contact_phone,
                            detail_data.contact_email,
                            detail_data.address,
                            detail_data.description,
                            str(detail_data.org_avatar) if detail_data.org_avatar else ""
                        ]
                        ws.append(row_data)
                    page += 1

                now_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                file_path = os.path.join(parent_file_path, f'组织列表_{now_time}.xlsx')
                wb.save(file_path)
                logger.info(f'组织 组织列表导出成功，文件路径：{file_path}')

            serializer_data = OrganizationResponseSerializer(pagination_data, many=True)
            return paginator.get_paginated_response({
                "status": status.HTTP_200_OK,
                "message": "获取组织列表成功",
                "data": serializer_data.data
            })
        except Exception as e:
            logger.error(f'组织 获取组织列表错误：{e}', exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误',
                'data': None
            })

    @api_doc(tag=["组织 组织列表导出"], response_body=EmptySerializer)
    @api_post
    def list_export(self, request):
        try:
            self.list(request, is_export=True)
            return Response({
                'status': status.HTTP_200_OK,
                'message': '组织列表导出成功',
                'data': None
            })
        except Exception as e:
            logger.error(f'组织 组织列表导出错误：{e}', exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误',
                'data': None
            })

    @api_doc(tag=["组织 组织列表文件导出下载"], response_body=EmptySerializer)
    @api_post
    def list_download(self, request, file_name):
        try:
            logger.info(f"组织 获取到的文件名是：{file_name}")
            file_path = os.path.join(os.path.dirname(__file__), self.EXPORT_DIR_NAME, file_name)
            if not os.path.exists(file_path):
                logger.error(f"组织 获取组织列表文件错误：文件不存在")
                return Response({
                    "status": status.HTTP_404_NOT_FOUND,
                    "message": "文件不存在",
                    "data": None
                })

            try:
                with open(file_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type=self.EXCEL_MIME_TYPE)
                    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{file_name}"
                    return response
            except PermissionError:
                logger.error(f"组织 文件下载错误：无读取权限，路径：{file_path}")
                return Response({
                    "status": status.HTTP_403_FORBIDDEN,
                    "message": "文件读取权限不足",
                    "data": None
                })
            except IOError as e:
                logger.error(f"组织 文件下载IO错误：{e}，路径：{file_path}")
                return Response({
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "文件读取失败",
                    "data": None
                })

        except Exception as e:
            logger.error(f'组织 组织数据导出文件下载错误：{e}', exc_info=True)
            return Response({
                'code': 500,
                'msg': f'文件下载失败: {str(e)}',
                'data': None
            })


class OrganizationRetrieveView(ViewSet):

    @api_doc(tag=["组织 获取单个组织信息"], response_body=OrganizationResponseSerializer)
    @api_get
    def retrieve(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        serializer_data = OrganizationResponseSerializer(org)
        logger.info(f'组织 获取单个组织信息成功，组织信息：{serializer_data.data}')
        return Response({
            "status": status.HTTP_200_OK,
            "message": "获取组织信息成功",
            "data": serializer_data.data
        })

    @api_doc(tag=["组织 社区组织注册"], request_body=OrganizationRequestSerializer,
             response_body=OrganizationResponseSerializer)
    @api_post
    def create(self, request):

        org_name = request.data.get("org_name")

        try:
            if Organization.objects.filter(org_name=org_name).exists():
                logger.error(f'组织 创建组织错误：组织 {org_name} 已存在')
                return Response({
                    "status": 400,
                    "message": "组织已存在",
                    "data": {}})

            params_data = OrganizationRequestSerializer(data=request.data)
            params_data.is_valid(raise_exception=True)
            params_data.save()
            serializer_data = OrganizationResponseSerializer(params_data.data)
            logger.info(f'组织 创建组织成功，创建组织信息：{serializer_data.data}')
            return Response({
                "status": status.HTTP_200_OK,
                "message": "创建组织成功",
                "data": serializer_data.data
            })
        except Exception as e:
            logger.error(f'组织 创建组织错误：{e}', exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误',
                'data': None
            })

    @api_doc(tag=["组织 社区组织信息更新"], request_body=OrganizationUpdateSerializer,
             response_body=OrganizationResponseSerializer)
    @api_put
    def update(self, request, pk):
        try:
            org = get_object_or_404(Organization, pk=pk)

            serializer = OrganizationUpdateSerializer(data=request.data, instance=org,
                                                      partial=True)  # partial=True 表示部分更新
            serializer.is_valid(raise_exception=True)  # 失败会返回400 错误
            serializer_data = serializer.save()

            logger.info(f'组织 单个组织更新成功，更新组织信息：{serializer.data}')
            response_serializer = OrganizationResponseSerializer(org)
            return Response({
                'status': status.HTTP_200_OK,
                'message': '社区组织更新成功',
                'data': response_serializer.data
            })

        except Exception as e:
            logger.error(f'组织 单个组织更新错误：{e}', exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误',
                'data': None
            })

    @api_doc(tag=["组织 删除单个组织"], request_body=OrganizationDeleteSerializer, response_body=EmptySerializer)
    @api_delete
    def destroy(self, request, pk):
        try:
            org = Organization.objects.get(pk=pk)
            org_name = org.org_name
            org.delete()
            logger.info(f'组织 单个组织删除成功，ID: {pk}，删除组织名称：{org_name}')
            return Response({
                'status': status.HTTP_204_NO_CONTENT,
                'message': '删除成功',
                'data': None
            })
        except Organization.DoesNotExist:
            logger.warning(f'组织 删除失败，组织不存在，ID: {pk}')
            return Response({
                'status': status.HTTP_404_NOT_FOUND,
                'message': f'组织不存在，ID: {pk}',
                'data': None
            })
        except Exception as e:
            logger.error(f'组织 单个组织删除错误：{e}', exc_info=True)
            return Response({
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': '服务器内部错误',
                'data': None
            })
