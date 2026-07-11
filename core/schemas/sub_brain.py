from dataclasses import dataclass


@dataclass(repr=False, slots=True)
class SubBrainConfig:
    """副脑配置参数"""

    cmd_enabled: bool = False
    """命令调用默认启用副脑"""
    tool_enabled: bool = False
    """工具调用默认启用副脑"""
    provider_id: str = ""
    """副脑模型供应商 ID"""
    system_prompt: str = ""
    """副脑系统提示词"""
