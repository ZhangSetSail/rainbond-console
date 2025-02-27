# -*- coding: utf8 -*-
import logging

from django.db.models import Q
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework_jwt.serializers import JSONWebTokenSerializer
from rest_framework_jwt.settings import api_settings

from django.contrib.auth import authenticate
from www.models.main import Users

jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

logger = logging.getLogger("default")


class CustomJWTSerializer(JSONWebTokenSerializer):
    username_field = 'nick_name'

    def validate(self, attrs):
        password = attrs.get("password")

        user_obj = Users.objects.filter(
            Q(phone=attrs.get("nick_name")) | Q(email=attrs.get("nick_name")) | Q(nick_name=attrs.get("nick_name"))).first()

        if user_obj is not None:
            credentials = {'username': user_obj.nick_name, 'password': password}
            if all(credentials.values()):
                user = authenticate(**credentials)
                if user:
                    if not user.is_active:
                        msg = _('用户帐户被禁用.')
                        raise serializers.ValidationError(msg)

                    payload = jwt_payload_handler(user)

                    return {'token': jwt_encode_handler(payload), 'user': user}
                else:
                    msg = _('无法使用提供的凭证登录.')
                    raise serializers.ValidationError(msg)

            else:
                msg = _('用户名或密码不能为空.')
                msg = msg.format(username_field=self.username_field)
                raise serializers.ValidationError(msg)

        else:
            msg = _('账户邮箱/用户名不存在')
            raise serializers.ValidationError(msg)


class ProbeSerilizer(serializers.Serializer):
    mode = serializers.CharField(max_length=10, required=True, help_text="探针模式")
    scheme = serializers.CharField(max_length=10, required=True, help_text="探针使用协议,tcp,http,cmd")

    path = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True, help_text="路径")
    port = serializers.IntegerField(required=True, help_text="检测端口")
    cmd = serializers.CharField(
        max_length=150, required=False, default="", allow_blank=True, allow_null=True, help_text="cmd 命令")
    http_header = serializers.CharField(
        max_length=300,
        default="",
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="http请求头，key=value,key2=value2")
    initial_delay_second = serializers.IntegerField(default=4, required=False, help_text="初始化等候时间")
    period_second = serializers.IntegerField(default=3, required=False, help_text="检测间隔时间")
    timeout_second = serializers.IntegerField(default=5, required=False, help_text="检测超时时间")
    failure_threshold = serializers.IntegerField(default=3, required=False, help_text="标志为失败的检测次数")
    success_threshold = serializers.IntegerField(default=1, required=False, help_text="标志为成功的检测次数")
    is_used = serializers.BooleanField(required=False, default=True, help_text="是否启用")


class ProbeUpdateSerilizer(serializers.Serializer):
    mode = serializers.CharField(max_length=10, required=True, help_text="探针模式")
    scheme = serializers.CharField(max_length=10, required=False, help_text="探针使用协议,tcp,http,cmd")

    path = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True, help_text="路径")
    port = serializers.IntegerField(required=True, help_text="检测端口")
    cmd = serializers.CharField(
        max_length=150, required=False, default="", allow_blank=True, allow_null=True, help_text="cmd 命令")
    http_header = serializers.CharField(
        max_length=300,
        default="",
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="http请求头，key=value,key2=value2")
    initial_delay_second = serializers.IntegerField(default=4, required=False, help_text="初始化等候时间")
    period_second = serializers.IntegerField(default=3, required=False, help_text="检测间隔时间")
    timeout_second = serializers.IntegerField(default=5, required=False, help_text="检测超时时间")
    failure_threshold = serializers.IntegerField(default=3, required=False, help_text="标志为失败的检测次数")
    success_threshold = serializers.IntegerField(default=1, required=False, help_text="标志为成功的检测次数")
    is_used = serializers.BooleanField(required=False, default=True, help_text="是否启用")


class TenantServiceUpdateSerilizer(serializers.Serializer):
    service_cname = serializers.CharField(max_length=100, required=False, help_text="组件名称")
    image = serializers.CharField(max_length=100, required=False, help_text="镜像")
    cmd = serializers.CharField(max_length=2048, required=False, help_text="启动参数")
    docker_cmd = serializers.CharField(max_length=2048, required=False, help_text="镜像创建命令")
    git_url = serializers.CharField(max_length=100, required=False, help_text="code代码仓库")
    min_memory = serializers.IntegerField(required=False, help_text="内存大小单位（M）")
    min_cpu = serializers.IntegerField(required=False, help_text="cpu分配额(单位：1000=1Core)")
    extend_method = serializers.CharField(max_length=32, required=False, help_text="组件类型")
    user_name = serializers.CharField(max_length=32, required=False, allow_blank=True, help_text="拉取仓库需要的用户名")
    password = serializers.CharField(max_length=32, required=False, allow_blank=True, help_text="拉取仓库需要的密码")
    job_strategy = serializers.CharField(max_length=2047, required=False, help_text="job任务策略")


class AppConfigGroupCreateSerilizer(serializers.Serializer):
    region_name = serializers.CharField(max_length=64, required=True, help_text="region name")
    config_group_name = serializers.CharField(max_length=64, required=True, help_text="application config group name")
    deploy_type = serializers.CharField(max_length=32, required=False, default="env", help_text="effective type")
    enable = serializers.BooleanField(required=False, default=False, help_text="effective status")
    service_ids = serializers.ListField(required=False, default=None, help_text="request bind service_ids")
    config_items = serializers.ListField(required=False, default=None, help_text="application config items")


class AppConfigGroupUpdateSerilizer(serializers.Serializer):
    service_ids = serializers.ListField(required=False, default=None, help_text="request bind service_ids")
    config_items = serializers.ListField(required=False, default=None, help_text="application config items")
    enable = serializers.BooleanField(required=False, default=False, help_text="effective status")
