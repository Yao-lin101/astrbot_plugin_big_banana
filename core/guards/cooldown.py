from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .whitelist import AccessCheck

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ..schemas import PreferenceConfig


class CooldownGuard:
    """冷却时间安全守卫，校验群组最近的绘图间隔。"""

    def __init__(self, preference_config: PreferenceConfig) -> None:
        self.preference_config = preference_config
        self.group_cooldowns: dict[str, float] = {}

    @property
    def cooldown_seconds(self) -> float:
        return self.preference_config.group_cooldown

    def cooldown_remaining(self, group_id: str | None) -> int | None:
        """计算群组绘图冷却剩余秒数。"""
        cooldown_seconds = self.cooldown_seconds
        if not group_id or cooldown_seconds <= 0:
            return None

        elapsed = time.time() - self.group_cooldowns.get(group_id, 0)
        if elapsed >= cooldown_seconds:
            return None
        return int(cooldown_seconds - elapsed)

    def mark_cooldown(self, group_id: str | None) -> None:
        """记录群组最近一次成功绘图时间。"""
        if group_id and self.cooldown_seconds > 0:
            self.group_cooldowns[group_id] = time.time()

    def check(self, event: AstrMessageEvent) -> AccessCheck:
        """检查当前群聊是否仍处于绘图冷却中。"""
        group_id = event.get_group_id()
        cooldown_seconds = self.cooldown_seconds
        remaining = self.cooldown_remaining(group_id)
        if remaining is None:
            return AccessCheck(allowed=True)

        return AccessCheck(
            allowed=False,
            message=f"当前群处于画图冷却中，冷却时间为 {cooldown_seconds} 秒，剩余 {remaining} 秒，请稍后再试。",
            log_message=f"[BIG BANANA] 群 {group_id} 处于冷却中，剩余 {remaining} 秒",
            remaining=remaining,
        )
