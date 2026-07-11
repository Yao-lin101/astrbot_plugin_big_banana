from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from astrbot.core import AstrBotConfig


@dataclass(frozen=True, slots=True)
class AccessCheck:
    """安全及访问检查结果。"""

    allowed: bool
    message: str = ""
    log_message: str = ""
    remaining: int | None = None


class WhitelistGuard:
    """白名单安全守卫，校验用户/群组是否允许绘图。"""

    def __init__(self, conf: AstrBotConfig) -> None:
        self.conf = conf

    def check(self, event: AstrMessageEvent, *, is_command: bool) -> AccessCheck:
        """根据命令来源和白名单配置判断事件是否允许绘图。"""
        whitelist_config = self.conf.get("whitelist_config", {})

        # 如果配置为“仅限制命令”，LLM 工具等非直接命令入口不走白名单限制。
        if not is_command and whitelist_config.get("only_for_commands", False):
            return AccessCheck(allowed=True)

        # 检查群组白名单，群组不允许时直接拦截。
        group_id = event.unified_msg_origin
        group_whitelist = [
            str(item) for item in whitelist_config.get("whitelist", [])
        ]
        if whitelist_config.get("enabled", False) and group_id not in group_whitelist:
            return AccessCheck(
                allowed=False,
                message="当前群不在白名单内，无法使用图片生成功能。",
                log_message=f"[BIG BANANA] 群 {group_id} 不在白名单内，跳过处理",
            )

        # 检查用户白名单，用户不允许时同样拦截。
        sender_id = event.get_sender_id()
        user_whitelist = [
            str(item) for item in whitelist_config.get("user_whitelist", [])
        ]
        if (
            whitelist_config.get("user_enabled", False)
            and sender_id not in user_whitelist
        ):
            return AccessCheck(
                allowed=False,
                message="该用户不在白名单内，无法使用图片生成功能。",
                log_message=f"[BIG BANANA] 用户 {sender_id} 不在白名单内，跳过处理",
            )

        return AccessCheck(allowed=True)
