from __future__ import annotations

import re
from collections.abc import Collection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


QQ_OFFICIAL_MENTION_RE = re.compile(r"<@!?([0-9A-Fa-f]{32})>")


def get_qq_official_mention_names(event: AstrMessageEvent) -> dict[str, str]:
    """读取 QQ 官方 Bot 原始消息中的 mention 昵称。返回 ID -> 昵称 映射。"""
    try:
        message_obj = getattr(event, "message_obj", None)
        raw_message = getattr(message_obj, "raw_message", None) if message_obj else None
    except AttributeError:
        raw_message = None
    if not raw_message:
        return {}
    mentions = getattr(raw_message, "mentions", ()) or ()
    names: dict[str, str] = {}
    for mention in mentions:
        mention_id = getattr(mention, "id", None)
        mention_name = getattr(mention, "username", None)
        if mention_id is not None and mention_name:
            names[str(mention_id)] = str(mention_name).strip()
    return names


def format_mention(
    user_id: str,
    nickname: str | None,
    duplicate_nicknames: Collection[str] = (),
) -> str:
    """按提示词约定格式化一个 mention。"""
    if not nickname:
        return user_id
    if nickname in duplicate_nicknames:
        return f"{nickname}({user_id})"
    return nickname
