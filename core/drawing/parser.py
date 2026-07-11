from __future__ import annotations

from typing import TYPE_CHECKING, Any

import astrbot.api.message_components as Comp

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ...main import BigBanana


def parse_params(plugin: BigBanana, event: AstrMessageEvent) -> dict[str, Any] | None:
    """解析消息事件中的绘图参数。未命中指令时快速返回 None。这里不负责收集图片，也不能修改消息链。"""

    # 提取首个有内容的 Plain 文本（目的是跳过开头是@的情况）
    first_text = ""
    first_component_idx = -1
    for idx, component in enumerate(event.get_messages()):
        if isinstance(component, Comp.Plain) and component.text.strip():
            first_text = component.text.strip()
            first_component_idx = idx
            break

    # 无有效文本，则不可能触发命令，直接返回 None
    if not first_text or first_component_idx == -1:
        return None

    # 命令前缀匹配
    matched_prefix = False
    for prefix in plugin.prefix_config.prefix_list:
        if first_text.startswith(prefix):
            # 去掉前缀，并去除前缀后的空格
            first_text = first_text.removeprefix(prefix).lstrip()
            matched_prefix = True
            break

    # 未 @ 机器人、未开启混合模式、配置了前缀但未匹配到前缀
    if (
        not event.is_at_or_wake_command
        and not plugin.prefix_config.coexist_enabled
        and plugin.prefix_config.prefix_list
        and not matched_prefix
    ):
        return None

    # 提供商前缀匹配
    provider_names: list[str] = []
    if plugin.prefix_config.provider_prefix:
        token, _, rest = first_text.partition(" ")
        # 如果第一个是提供商，那么必须存在剩余的文本才能匹配到预设，所以剩余文本的非空判断是必要的
        if token and rest:
            # token按逗号分割
            tokens = token.split(",")
            for t in tokens:
                provider_name = t.strip()
                template_config = plugin.provider_config_manager.provider_configs.get(
                    provider_name
                )
                if template_config:
                    provider_name = template_config.name
                elif provider_name not in plugin.conf.get("default_astr_providers", []):
                    provider_name = None
                # 匹配成功，去除提供商前缀和后续空格
                if provider_name:
                    provider_names.append(provider_name)
            if provider_names:
                first_text = rest.lstrip()

    # 提取预设指令和该组件内剩余文本
    cmd, _, cmd_rest = first_text.partition(" ")
    cmd = cmd.strip()

    # 匹配到预设是必须的
    if not cmd or cmd not in plugin.prompt_config_manager.prompt_config:
        return None

    # 复制预设参数，防止污染全局预设。
    # 上游约束了非引用类型，这里只需浅拷贝即可。
    params = plugin.prompt_config_manager.prompt_config[cmd].copy()
    # 如果有手动指定提供商，将覆盖预设中的提供商
    if provider_names:
        params["providers"] = provider_names

    preset_prompt = params.get("prompt", "")
    should_append_user_text = params.get(
        "preset_append", plugin.common_config.preset_append
    )
    # 有占位符时替换指定位置；启用补充时把用户文本追加到固定预设后。
    if "{{user_text}}" in preset_prompt or should_append_user_text:
        message_parts = []
        for idx, comp in enumerate(event.get_messages()):
            if idx == first_component_idx:
                if cmd_rest:
                    # cmd_rest已经去掉了所有前缀，直接代替第一个文本组件内容
                    message_parts.append(cmd_rest)
            elif isinstance(comp, Comp.Plain) and comp.text:
                message_parts.append(comp.text)
            elif isinstance(comp, Comp.At) and comp.qq:
                message_parts.append(f"@{comp.name}({comp.qq})")
        # 组装完整的用户输入文本
        user_text = " ".join(message_parts).strip()
        # 解析用户输入文本中的参数
        user_params = plugin.prompt_config_manager.parse_prompt_params(user_text)
        # 取出并删除用户提示词
        user_prompt = user_params.pop("prompt", "")
        if "{{user_text}}" in preset_prompt:
            params["prompt"] = preset_prompt.replace("{{user_text}}", user_prompt)
        elif user_prompt:
            params["prompt"] = f"{preset_prompt.rstrip()} {user_prompt}".strip()
        # 更新参数
        params.update(user_params)

    return params
