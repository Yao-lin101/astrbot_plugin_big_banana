from __future__ import annotations

from typing import TYPE_CHECKING

from astrbot.api import logger

from ..schemas import ProviderConfig

if TYPE_CHECKING:
    from astrbot.core import AstrBotConfig


class ProviderConfigManager:
    """提供商配置"""

    def __init__(self, conf: AstrBotConfig):
        self.conf = conf
        self.provider_configs = self._build_provider_configs()
        self.default_providers = self._build_default_providers()

    def _build_default_providers(self) -> list[str]:
        """按优先级返回提供商名称列表"""
        # 优先级、类型权重（模板提供商权重高于原生提供商）、模板索引（同优先级数字，优先级与索引成反比）、提供商名称
        entries: list[tuple[int, int, int, str]] = []

        # 收集模板提供商
        for index, raw_item in enumerate(self.conf["provider_template"]):
            name = raw_item.get("name", "").strip()
            if name and raw_item["enabled"] and raw_item["enabled_as_default"]:
                entries.append((raw_item["fallback_order"], 0, index, name))

        # 收集原生提供商
        for index, provider_name in enumerate(
            self.conf.get("default_astr_providers", [])
        ):
            entries.append((0, 1, index, provider_name))

        # 从左到右逐项比较，任意一项不同，则数字小的靠前（从小到大排序），同则继续比较下一项
        return [provider_name for _, _, _, provider_name in sorted(entries)]

    def _build_provider_configs(self) -> dict[str, ProviderConfig]:
        """解析模板提供商"""
        result: dict[str, ProviderConfig] = {}
        for raw_item in self.conf.get("provider_template", []):
            name = raw_item.get("name", "").strip()
            if not name:
                logger.warning("[BIG BANANA] 跳过未命名的提供商配置")
                continue
            if name in result:
                logger.warning(f"[BIG BANANA] 模板提供商名称重复，已跳过 {name}")
                continue
            result[name] = ProviderConfig(
                provider_type=raw_item.get("provider_type", ""),
                capability=raw_item.get("capability", "image_generation"),
                enabled=raw_item.get("enabled", False),
                name=name,
                enabled_as_default=raw_item.get("enabled_as_default", True),
                fallback_order=raw_item.get("fallback_order", 0),
                keys=raw_item.get("keys", []),
                base_url=raw_item.get("base_url", "").strip().rstrip("/"),
                model=raw_item.get("model", ""),
                stream=raw_item.get("stream", False),
                enable_proxy=raw_item.get("enable_proxy", False),
                raw_config=raw_item,
            )
        return result
