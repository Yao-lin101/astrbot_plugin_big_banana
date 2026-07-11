from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.core.utils.session_waiter import session_waiter

from ...schemas import PARAMS_LIST

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    from astrbot.api.event import AstrMessageEvent
    from astrbot.core.message.message_event_result import MessageEventResult
    from astrbot.core.utils.session_waiter import SessionController

    from ...config.prompt_config import PromptConfigManager


@dataclass(frozen=True, slots=True)
class _PromptEntry:
    index: int
    raw_command: str
    prompt_text: str
    triggers: tuple[str, ...]

    @property
    def is_multi_trigger(self) -> bool:
        return len(self.triggers) > 1 or (
            self.raw_command.startswith("[") and self.raw_command.endswith("]")
        )


class PromptHandler:
    """提示词管理命令处理器。"""

    def __init__(self, prompt_config_manager: PromptConfigManager) -> None:
        """注入提示词存储服务供命令处理使用。"""
        self.prompt_config_manager = prompt_config_manager

    def _upsert_prompt(self, trigger_word: str, prompt_text: str) -> str:
        """新增或更新单个触发词对应的提示词。"""
        build_prompt = f"{trigger_word} {prompt_text.strip()}"
        prompt_list = list(self.prompt_config_manager.conf.get("prompt", []))
        action = "添加"

        if trigger_word in self.prompt_config_manager.prompt_config:
            action = "更新"
            for index, item in enumerate(prompt_list):
                entry = self._parse_prompt_entry(index, item)
                if entry is None:
                    continue
                if entry.raw_command == trigger_word:
                    prompt_list[index] = build_prompt
                    break
                if trigger_word in entry.triggers:
                    remaining = tuple(
                        trigger for trigger in entry.triggers if trigger != trigger_word
                    )
                    if remaining:
                        prompt_list[index] = self._format_prompt_entry(
                            remaining, entry.prompt_text
                        )
                    else:
                        del prompt_list[index]
                    prompt_list.append(build_prompt)
                    break
        else:
            prompt_list.append(build_prompt)

        self._save_prompt_list(prompt_list)
        return action

    def _find_entry(self, trigger_word: str) -> _PromptEntry | None:
        """查找包含指定触发词的提示词条目。"""
        for index, item in enumerate(self.prompt_config_manager.conf.get("prompt", [])):
            entry = self._parse_prompt_entry(index, item)
            if entry and trigger_word in entry.triggers:
                return entry
        return None

    def _delete_entry(self, index: int) -> None:
        """按索引删除整个提示词条目。"""
        prompt_list = list(self.prompt_config_manager.conf.get("prompt", []))
        if 0 <= index < len(prompt_list):
            del prompt_list[index]
            self._save_prompt_list(prompt_list)

    def _remove_trigger_from_entry(self, index: int, trigger_word: str) -> None:
        """从多触发词条目中移除指定触发词。"""
        prompt_list = list(self.prompt_config_manager.conf.get("prompt", []))
        if not 0 <= index < len(prompt_list):
            return

        entry = self._parse_prompt_entry(index, prompt_list[index])
        if entry is None or trigger_word not in entry.triggers:
            return

        remaining = tuple(
            trigger for trigger in entry.triggers if trigger != trigger_word
        )
        if remaining:
            prompt_list[index] = self._format_prompt_entry(remaining, entry.prompt_text)
        else:
            del prompt_list[index]
        self._save_prompt_list(prompt_list)

    def _save_prompt_list(self, prompt_list: list[str]) -> None:
        """写回提示词列表并刷新解析缓存。"""
        self.prompt_config_manager.conf["prompt"] = prompt_list
        self.prompt_config_manager.conf.save_config()
        self.prompt_config_manager.prompt_config = (
            self.prompt_config_manager._build_prompt_config()
        )

    @staticmethod
    def _parse_prompt_entry(index: int, item: str) -> _PromptEntry | None:
        """把原始提示词配置行解析为结构化条目。"""
        raw_command, _, prompt_text = item.strip().partition(" ")
        if not raw_command:
            return None
        if raw_command.startswith("[") and raw_command.endswith("]"):
            triggers = tuple(
                trigger.strip()
                for trigger in raw_command[1:-1].split(",")
                if trigger.strip()
            )
        else:
            triggers = (raw_command,)
        return _PromptEntry(index, raw_command, prompt_text, triggers)

    @staticmethod
    def _format_prompt_entry(triggers: Sequence[str], prompt_text: str) -> str:
        """把触发词列表和提示词正文重新格式化为配置行。"""
        if len(triggers) == 1:
            return f"{triggers[0]} {prompt_text}"
        return f"[{','.join(triggers)}] {prompt_text}"

    async def add_prompt(
        self, event: AstrMessageEvent, trigger_word: str = ""
    ) -> AsyncGenerator[MessageEventResult, None]:
        """开启交互式流程新增或更新预设提示词。"""
        if not trigger_word:
            yield event.plain_result("❌ 格式错误：lm添加 (触发词)")
            return

        yield event.plain_result(
            f"🍌 正在为触发词 「{trigger_word}」 添加/更新提示词\n"
            f"✦ 请在120秒内输入完整的提示词内容（不含触发词，包含参数）\n"
            f"✦ 输入「取消」可取消操作。"
        )

        @session_waiter(timeout=120, record_history_chains=False)
        async def waiter(controller: SessionController, waiter_event: AstrMessageEvent):
            """处理交互式命令的后续用户回复。"""
            if waiter_event.get_sender_id() != event.get_sender_id():
                return

            prompt_text = waiter_event.message_str.strip()
            if prompt_text == "取消":
                await waiter_event.send(waiter_event.plain_result("🍌 操作已取消。"))
                controller.stop()
                return
            if not prompt_text:
                await waiter_event.send(
                    waiter_event.plain_result("❌ 提示词正文不能为空，请重新输入。")
                )
                return

            action = self._upsert_prompt(trigger_word, prompt_text)
            await waiter_event.send(
                waiter_event.plain_result(
                    f"✅ 已成功{action}提示词：「{trigger_word}」"
                )
            )
            controller.stop()

        try:
            await waiter(event)
        except TimeoutError:
            yield event.plain_result("❌ 超时了，操作已取消！")
        except Exception as e:
            logger.error(f"大香蕉添加提示词出现错误: {e}", exc_info=True)
            yield event.plain_result("❌ 处理时发生了一个内部错误。")
        finally:
            event.stop_event()

    async def list_prompts(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[MessageEventResult, None]:
        """输出所有已注册的预设触发词。"""
        prompts = list(self.prompt_config_manager.prompt_config.keys())
        if not prompts:
            yield event.plain_result("当前没有预设提示词。")
            return

        msg = "📜 当前预设提示词列表：\n" + "、".join(prompts)
        yield event.plain_result(msg)

    async def prompt_details(
        self, event: AstrMessageEvent, trigger_word: str
    ) -> AsyncGenerator[MessageEventResult, None]:
        """输出指定预设提示词的正文和参数。"""
        prompt_config = self.prompt_config_manager.prompt_config
        if trigger_word not in prompt_config:
            yield event.plain_result(f"❌ 未找到提示词：「{trigger_word}」")
            return

        params = prompt_config[trigger_word]
        details = [f"📋 提示词详情：「{trigger_word}」"]
        details.append(params.get("prompt", ""))
        for key in PARAMS_LIST:
            if key in params:
                details.append(f"{key}: {params[key]}")
        if event.platform_meta.name == "aiocqhttp":
            from astrbot.api.message_components import Node, Nodes, Plain

            nodes = []
            for detail in details:
                nodes.append(
                    Node(
                        uin=event.get_sender_id(),
                        name=event.get_sender_name(),
                        content=[Plain(detail)],
                    )
                )
            yield event.chain_result([Nodes(nodes)])
        else:
            yield event.plain_result("\n".join(details))

    async def del_prompt(
        self, event: AstrMessageEvent, trigger_word: str = ""
    ) -> AsyncGenerator[MessageEventResult, None]:
        """删除单触发词或多触发词中的指定预设。"""
        if not trigger_word:
            yield event.plain_result("❌ 格式错误：lm删除 (触发词)")
            return

        entry = self._find_entry(trigger_word)
        if entry is None:
            yield event.plain_result(f"❌ 未找到提示词：「{trigger_word}」")
            return

        if not entry.is_multi_trigger:
            self._delete_entry(entry.index)
            yield event.plain_result(f"🗑️ 已删除提示词：「{trigger_word}」")
            return

        yield event.plain_result(
            "⚠️ 检测到该提示词为多触发词配置，请选择删除方案\n"
            "A. 单独删除该触发词\n"
            "B. 删除整个提示词\n"
            "C. 取消操作"
        )

        @session_waiter(timeout=60, record_history_chains=False)
        async def waiter(controller: SessionController, waiter_event: AstrMessageEvent):
            """处理交互式命令的后续用户回复。"""
            # 必须是操作者回复，否则忽略
            if waiter_event.get_sender_id() != event.get_sender_id():
                return

            reply_content = waiter_event.message_str.strip().upper()
            if reply_content not in ["A", "B", "C"]:
                await waiter_event.send(
                    waiter_event.plain_result("❌ 请输入有效的选项：A、B 或 C。")
                )
                return

            current_entry = self._find_entry(trigger_word)
            if current_entry is None:
                await waiter_event.send(
                    waiter_event.plain_result(f"❌ 未找到提示词：「{trigger_word}」")
                )
                controller.stop()
                return

            if reply_content == "C":
                await waiter_event.send(waiter_event.plain_result("🍌 操作已取消。"))
                controller.stop()
                return
            if reply_content == "B":
                self._delete_entry(current_entry.index)
                await waiter_event.send(
                    waiter_event.plain_result(
                        f"🗑️ 已删除多触发提示词：{current_entry.raw_command}"
                    )
                )
                controller.stop()
                return
            if reply_content == "A":
                self._remove_trigger_from_entry(current_entry.index, trigger_word)
                await waiter_event.send(
                    waiter_event.plain_result(
                        f"🗑️ 已从多触发提示词中移除：「{trigger_word}」"
                    )
                )
                controller.stop()

        try:
            await waiter(event)
        except TimeoutError:
            yield event.plain_result("❌ 超时了，操作已取消！")
        except Exception as e:
            logger.error(f"大香蕉删除提示词出现错误: {e}", exc_info=True)
            yield event.plain_result("❌ 处理时发生了一个内部错误。")
        finally:
            event.stop_event()
