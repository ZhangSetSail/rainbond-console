from rest_framework.response import Response
from console.models.main import RoleInfo, UserRole, AuditLog
from rest_framework import status
import json
import logging
from console.views.base import JWTAuthApiView
from django.db import transaction
from console.repositories.user_repo import user_repo

logger = logging.getLogger('console')

class AuditTestView(JWTAuthApiView):
    def post(self, request):
        """测试审计功能"""
        # 确保请求中间件正确设置
        from console.services.audit_service import set_current_request
        set_current_request(request)

        try:
            logger.info("Starting audit test...")
            
            # 获取当前用户
            user = user_repo.get_user_by_user_id(request.user.user_id)
            if not user:
                return Response({
                    'status': 'error',
                    'message': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)

            logger.info(f"Current user: {user.user_id} ({user.nick_name})")

            with transaction.atomic():
                # 创建角色
                role = RoleInfo.objects.create(
                    name="测试角色",
                    kind_id="test_kind",
                    kind="test"
                )
                logger.info(f"Created test role with ID: {role.ID}")

                # 创建用户角色
                user_role = UserRole.objects.create(
                    user_id=str(user.user_id),
                    role_id=str(role.ID)
                )
                logger.info(f"Created test user role with ID: {user_role.ID}")

                # 更新用户角色
                old_user_id = user_role.user_id
                user_role.user_id = str(user.user_id)
                user_role.save()
                logger.info(f"Updated user role {user_role.ID} from {old_user_id} to {user_role.user_id}")

                # 删除用户角色
                user_role_id = user_role.ID
                user_role.delete()
                logger.info(f"Deleted user role with ID: {user_role_id}")

                # 删除角色
                role.delete()
                logger.info(f"Deleted role with ID: {role.ID}")

            # 获取审计日志 - 在事务之外查询
            audit_logs = AuditLog.objects.all().order_by('-created_time')
            logger.info(f"Found {audit_logs.count()} audit log entries")

            # 格式化日志数据
            logs_data = []
            for log in audit_logs:
                try:
                    old_data = json.loads(log.old_data) if log.old_data else None
                    new_data = json.loads(log.new_data) if log.new_data else None
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON data for log {log.ID}: {str(e)}")
                    old_data = None
                    new_data = None

                log_data = {
                    'id': log.ID,
                    'user_id': log.user_id,
                    'username': log.username,
                    'action': log.action,
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id,
                    'old_data': old_data,
                    'new_data': new_data,
                    'ip_address': log.ip_address,
                    'created_time': log.created_time.strftime('%Y-%m-%d %H:%M:%S')
                }
                logs_data.append(log_data)
                logger.debug(f"Audit log entry: {log_data}")

            return Response({
                'status': 'success',
                'message': '审计测试完成',
                'audit_logs': logs_data,
                'current_user': {
                    'user_id': user.user_id,
                    'nick_name': user.nick_name
                }
            })

        except Exception as e:
            logger.error(f"Error in audit test: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            # 清理请求上下文
            set_current_request(None)
