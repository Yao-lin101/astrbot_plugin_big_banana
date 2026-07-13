import json
from pathlib import Path

from core.schemas import LlmToolsConfig, PreferenceConfig

ROOT = Path(__file__).resolve().parents[1]


def test_background_tasks_are_disabled_by_default() -> None:
    assert PreferenceConfig().command_use_background_task is False
    assert LlmToolsConfig().llm_tool_use_background_task is False
    assert LlmToolsConfig().llm_tool_truncate_images is False


def test_background_tasks_are_disabled_in_config_schema() -> None:
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))

    assert (
        schema["preference_config"]["items"]["command_use_background_task"]["default"]
        is False
    )
    assert (
        schema["llm_tools"]["items"]["llm_tool_use_background_task"]["default"]
        is False
    )
    assert (
        schema["llm_tools"]["items"]["llm_tool_truncate_images"]["default"] is False
    )


def test_vertex_anonymous_retry_controls_are_in_provider_template() -> None:
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    default_provider = schema["provider_template"]["default"][0]
    provider_items = schema["provider_template"]["templates"][
        "vertex_ai_anonymous"
    ]["items"]

    assert default_provider["max_refresh"] == 5
    assert default_provider["retry_before_switch"] == 5
    assert default_provider["retry_delay"] == 1
    assert "max_retry" not in default_provider
    assert provider_items["max_refresh"]["default"] == 5
    assert provider_items["retry_before_switch"]["default"] == 5
    assert provider_items["retry_delay"]["default"] == 1
    assert "max_retry" not in provider_items
