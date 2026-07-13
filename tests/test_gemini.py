import json
from pathlib import Path
from types import SimpleNamespace

from core.providers.gemini import GeminiProvider
from core.schemas import ProviderConfig

ROOT = Path(__file__).resolve().parents[1]


def build_body(system_prompt: str | None = None) -> dict:
    plugin = SimpleNamespace(
        params_config=SimpleNamespace(
            aspect_ratio="default",
            google_search=False,
            image_size="1K",
        )
    )
    raw_config = {"response_modalities": "['IMAGE']"}
    if system_prompt is not None:
        raw_config["system_prompt"] = system_prompt
    config = ProviderConfig(
        provider_type="Gemini",
        name="gemini",
        model="gemini-3-pro-image",
        raw_config=raw_config,
    )
    provider = GeminiProvider(plugin, config, {"prompt": "test"})
    provider._body_context_cache = None
    return provider._build_body_context()


def test_system_prompt_is_passed_as_system_instruction() -> None:
    body = build_body("Always use watercolor style.")

    assert body["systemInstruction"] == {
        "parts": [{"text": "Always use watercolor style."}]
    }


def test_system_instruction_is_omitted_when_prompt_is_empty_or_missing() -> None:
    assert "systemInstruction" not in build_body("")
    assert "systemInstruction" not in build_body()


def test_system_prompt_is_available_in_gemini_provider_config() -> None:
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    system_prompt = schema["provider_template"]["templates"]["gemini"]["items"][
        "system_prompt"
    ]

    assert system_prompt["type"] == "text"
    assert system_prompt["default"] == ""
