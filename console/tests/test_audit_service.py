from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from console.models.main import AuditLog, UserRole, RoleInfo
from console.services.audit_service import AuditService, set_current_request
import json
from datetime import datetime, timedelta


class MockUser:
    def __init__(self):
        self.user_id = 1
        self.nick_name = "test_user"


class MockRequest:
    def __init__(self):
        self.user = MockUser()
        self.META = {
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_USER_AGENT': 'Mozilla/5.0 (Test Browser)'
        }


class AuditServiceTest(TestCase):
    def setUp(self):
        # 设置模拟请求
        self.request = MockRequest()
        set_current_request(self.request)
        
        # 创建测试角色
        self.role = RoleInfo.objects.create(
            name="测试角色",
            kind_id="test_kind",
            kind="test"
        )

    def tearDown(self):
        # 清理测试数据
        RoleInfo.objects.all().delete()
        UserRole.objects.all().delete()
        AuditLog.objects.all().delete()
        set_current_request(None)

    def test_create_audit_log(self):
        """测试创建操作的审计日志"""
        # 创建用户角色
        user_role = UserRole.objects.create(
            user_id="test_user",
            role_id=str(self.role.ID)
        )

        # 检查是否创建了审计日志
        audit_logs = AuditLog.objects.filter(
            action='create',
            resource_type='userrole'
        )
        self.assertEqual(audit_logs.count(), 1)
        
        log = audit_logs.first()
        self.assertEqual(log.user_id, self.request.user.user_id)
        self.assertEqual(log.username, self.request.user.nick_name)
        self.assertEqual(log.resource_id, str(user_role.ID))
        self.assertIsNone(log.old_data)
        self.assertIsNotNone(log.new_data)

    def test_update_audit_log(self):
        """测试更新操作的审计日志"""
        # 创建用户角色
        user_role = UserRole.objects.create(
            user_id="test_user",
            role_id=str(self.role.ID)
        )

        # 更新用户角色
        user_role.user_id = "updated_user"
        user_role.save()

        # 检查是否创建了审计日志
        audit_logs = AuditLog.objects.filter(
            action='update',
            resource_type='userrole'
        )
        self.assertEqual(audit_logs.count(), 1)
        
        log = audit_logs.first()
        self.assertIsNotNone(log.old_data)
        self.assertIsNotNone(log.new_data)
        
        # 验证old_data和new_data
        old_data = json.loads(log.old_data)
        new_data = json.loads(log.new_data)
        self.assertEqual(old_data['user_id'], "test_user")
        self.assertEqual(new_data['user_id'], "updated_user")

    def test_delete_audit_log(self):
        """测试删除操作的审计日志"""
        # 创建用户角色
        user_role = UserRole.objects.create(
            user_id="test_user",
            role_id=str(self.role.ID)
        )
        user_role_id = user_role.ID

        # 删除用户角色
        user_role.delete()

        # 检查是否创建了审计日志
        audit_logs = AuditLog.objects.filter(
            action='delete',
            resource_type='userrole'
        )
        self.assertEqual(audit_logs.count(), 1)
        
        log = audit_logs.first()
        self.assertEqual(log.resource_id, str(user_role_id))
        self.assertIsNotNone(log.old_data)
        self.assertIsNone(log.new_data)

    def test_get_audit_logs(self):
        """测试审计日志查询"""
        # 创建多个用户角色
        for i in range(3):
            UserRole.objects.create(
                user_id=f"test_user_{i}",
                role_id=str(self.role.ID)
            )

        # 测试不同的查询条件
        # 1. 按资源类型查询
        logs = AuditService.get_audit_logs(resource_type='userrole')
        self.assertEqual(logs.count(), 3)

        # 2. 按操作类型查询
        logs = AuditService.get_audit_logs(action='create')
        self.assertEqual(logs.count(), 3)

        # 3. 按时间范围查询
        start_time = datetime.now() - timedelta(minutes=5)
        end_time = datetime.now() + timedelta(minutes=5)
        logs = AuditService.get_audit_logs(
            start_time=start_time,
            end_time=end_time
        )
        self.assertEqual(logs.count(), 3)

        # 4. 按用户ID查询
        logs = AuditService.get_audit_logs(user_id=self.request.user.user_id)
        self.assertEqual(logs.count(), 3)
