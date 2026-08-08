from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import astrbot.api.message_components as Comp
from astrbot.api import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from astrbot.core.message.components import BaseMessageComponent


class QuoteReplyMode(str, Enum):
    """回复引用模式枚举。"""

    BOTH = "both"
    COMMAND_ONLY = "command_only"
    TOOL_ONLY = "tool_only"
    NONE = "none"

    @classmethod
    def from_str(cls, value: str | None) -> QuoteReplyMode:
        """从字符串安全的解析 QuoteReplyMode，支持选项别名。"""
        if not value:
            return cls.BOTH
        val = str(value).strip().lower()
        if val in ("command_only", "command", "2", "仅命令"):
            return cls.COMMAND_ONLY
        if val in ("tool_only", "tool", "3", "仅工具"):
            return cls.TOOL_ONLY
        if val in ("none", "4", "不引用回复", "false"):
            return cls.NONE
        return cls.BOTH

    def should_quote(self, is_command: bool) -> bool:
        """根据当前模式和调用类型决定是否引用回复。"""
        if self == QuoteReplyMode.NONE:
            return False
        if is_command and self == QuoteReplyMode.TOOL_ONLY:
            return False
        if not is_command and self == QuoteReplyMode.COMMAND_ONLY:
            return False
        return True


def get_message_id(event: AstrMessageEvent) -> str | None:
    """安全获取事件关联的消息 ID，若不存在或不是有效 message_obj 则返回 None。"""
    try:
        message_obj = getattr(event, "message_obj", None)
        if message_obj is None:
            return None
        message_id = getattr(message_obj, "message_id", None)
        if message_id is None:
            return None
        id_str = str(message_id).strip()
        return id_str if id_str != "" else None
    except (AttributeError, TypeError):
        return None


def build_reply_component(
    event: AstrMessageEvent,
    is_command: bool = True,
    plugin: Any = None,
) -> BaseMessageComponent | None:
    """若满足配置的回复引用条件且事件中包含有效 message_id，则构造 Reply 引用组件，否则返回 None。"""
    if plugin and hasattr(plugin, "preference_config"):
        raw_mode = getattr(plugin.preference_config, "quote_reply_mode", "both")
        mode = QuoteReplyMode.from_str(raw_mode)
        if not mode.should_quote(is_command):
            return None

    message_id = get_message_id(event)
    if message_id is not None:
        return Comp.Reply(id=message_id)
    return None


def build_image_component(
    image: Any, fallback_url: str | None = None
) -> BaseMessageComponent:
    """为 ImageResource 优先按 URL、本地文件、Base64 顺序构建最可靠的 Comp.Image。"""
    url_val = getattr(image, "url", None) or fallback_url
    if url_val:
        url_str = str(url_val).strip()
        parsed = urlparse(url_str)
        if parsed.scheme in ("http", "https"):
            return Comp.Image.fromURL(url_str)
        elif parsed.scheme == "file":
            clean_path = parsed.path or url_str.removeprefix("file://")
            return Comp.Image.fromFileSystem(clean_path)
        elif parsed.scheme == "" and os.path.isabs(url_str):
            return Comp.Image.fromFileSystem(url_str)
        else:
            return Comp.Image.fromURL(url_str)
    b64 = getattr(image, "base64", None)
    if b64:
        return Comp.Image.fromBase64(b64)
    if fallback_url:
        return Comp.Image.fromURL(fallback_url)
    logger.warning("[BIG BANANA] 图片无法构建组件：既无有效 URL/Path 也无 Base64 数据")
    return Comp.Plain("❌ 图片无法加载")
