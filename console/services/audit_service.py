from console.models.main import AuditLog
from django.forms.models import model_to_dict
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from django.apps import apps
from django.db import transaction
import threading
import json
import logging
from datetime import datetime
from dateutil import parser
from datetime import date, time
from django.db import models

# 配置日志
logger = logging.getLogger('console')

# 需要审计的模型列表
AUDITED_MODELS = [
    'UserRole',  # 用户角色
    'RoleInfo',  # 角色信息
    'RolePerms',  # 角色权限
    # 在这里添加其他需要审计的模型
]

def init_audit_service():
    """初始化审计服务，注册信号处理器"""
    logger.info("Initializing audit service...")
    
    # 获取所有需要审计的模型
    for model_name in AUDITED_MODELS:
        try:
            model = apps.get_model('console', model_name)
            logger.info(f"Registering audit signals for model: {model_name}")
            
            # 为每个模型注册信号
            pre_save.connect(pre_save_handler, sender=model)
            post_save.connect(post_save_handler, sender=model)
            pre_delete.connect(pre_delete_handler, sender=model)
            
        except LookupError as e:
            logger.error(f"Failed to register audit signals for model {model_name}: {str(e)}")

def get_field_verbose_name(model, field_name):
    """获取模型字段的中文名称"""
    try:
        field = model._meta.get_field(field_name)
        return field.help_text or field.verbose_name or field_name
    except:
        return field_name

def model_to_json_dict(instance):
    """将模型实例转换为JSON可序列化的字典，使用中文字段名"""
    if instance is None:
        return None
    if isinstance(instance, dict):
        return instance
    
    result = {}
    # 转换字段值
    for field in instance._meta.fields:
        field_value = getattr(instance, field.name, None)
        if isinstance(field_value, datetime):
            field_value = field_value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(field_value, (date, time)):
            field_value = str(field_value)
        
        # 使用中文字段名
        field_name = get_field_verbose_name(instance, field.name)
        result[field_name] = field_value
    
    return result

def create_audit_log(action, resource_type, resource_id, old_data=None, new_data=None):
    """创建审计日志"""
    try:
        request = get_current_request()
        if not request or not request.user:
            logger.warning("No request context or user found when creating audit log")
            return

        # 获取用户信息
        try:
            from console.repositories.user_repo import user_repo
            user = user_repo.get_user_by_user_id(request.user.user_id)
            if not user:
                logger.error(f"User not found: {request.user.user_id}")
                return
            user_id = user.user_id
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return

        # 获取表名
        table_name = ""
        if isinstance(old_data, models.Model):
            table_name = getattr(old_data._meta, 'verbose_name', old_data._meta.object_name)
        elif isinstance(new_data, models.Model):
            table_name = getattr(new_data._meta, 'verbose_name', new_data._meta.object_name)

        # 转换数据为可JSON序列化的格式
        old_data_dict = model_to_json_dict(old_data)
        new_data_dict = model_to_json_dict(new_data)

        # 创建审计日志
        AuditLog.objects.create(
            user_id=user_id,
            username=user.nick_name,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            table_name=table_name,
            old_data=json.dumps(old_data_dict, ensure_ascii=False) if old_data_dict else None,
            new_data=json.dumps(new_data_dict, ensure_ascii=False) if new_data_dict else None,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
    except Exception as e:
        logger.error(f"Error creating audit log: {str(e)}", exc_info=True)

# 使用线程本地存储来存储请求上下文
_thread_locals = threading.local()

def get_current_request():
    return getattr(_thread_locals, 'request', None)

def set_current_request(request):
    _thread_locals.request = request

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("Audit middleware initialized")

    def __call__(self, request):
        # 在处理请求前设置请求对象
        set_current_request(request)
        try:
            response = self.get_response(request)
            return response
        finally:
            # 确保在请求处理完后清理
            set_current_request(None)

def should_audit_model(sender):
    """判断模型是否需要审计"""
    return sender.__name__ in AUDITED_MODELS

@receiver(pre_save)
def pre_save_handler(sender, instance, **kwargs):
    """处理更新操作，保存更新前的数据"""
    if not should_audit_model(sender):
        return

    try:
        if instance.pk:
            # 获取数据库中现有的实例
            old_instance = sender.objects.get(pk=instance.pk)
            # 保存旧数据用于审计
            instance._audit_old_data = old_instance
    except ObjectDoesNotExist:
        # 如果是新创建的实例，不需要保存旧数据
        pass
    except Exception as e:
        logger.error(f"Error in pre_save_handler: {str(e)}", exc_info=True)

@receiver(post_save)
def post_save_handler(sender, instance, created, **kwargs):
    """处理创建和更新操作的审计"""
    if not should_audit_model(sender):
        return

    try:
        action = 'create' if created else 'update'
        old_data = None if created else getattr(instance, '_audit_old_data', None)
        
        create_audit_log(
            action=action,
            resource_type=sender.__name__.lower(),
            resource_id=str(instance.pk),
            old_data=old_data,
            new_data=instance
        )
    except Exception as e:
        logger.error(f"Error in post_save_handler: {str(e)}", exc_info=True)

@receiver(pre_delete)
def pre_delete_handler(sender, instance, **kwargs):
    """处理删除操作的审计"""
    if not should_audit_model(sender):
        return

    try:
        create_audit_log(
            action='delete',
            resource_type=sender.__name__.lower(),
            resource_id=str(instance.pk),
            old_data=instance,
            new_data=None
        )
    except Exception as e:
        logger.error(f"Error in pre_delete_handler: {str(e)}", exc_info=True)

def _get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class AuditService(object):
    @staticmethod
    def get_audit_logs(resource_type=None, resource_id=None, user_id=None, action=None, start_time=None, end_time=None):
        """
        获取审计日志
        
        参数:
            resource_type: 资源类型（可选）
            resource_id: 资源ID（可选）
            user_id: 用户ID（可选）
            action: 操作类型（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
        """
        logger.debug(f"Querying audit logs with filters: type={resource_type}, id={resource_id}, user={user_id}, action={action}")
        
        queryset = AuditLog.objects.all()
        
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        if resource_id:
            queryset = queryset.filter(resource_id=resource_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action:
            queryset = queryset.filter(action=action)
        if start_time:
            queryset = queryset.filter(created_time__gte=start_time)
        if end_time:
            queryset = queryset.filter(created_time__lte=end_time)
            
        results = queryset.order_by('-created_time')
        logger.info(f"Found {results.count()} audit log entries")
        return results
