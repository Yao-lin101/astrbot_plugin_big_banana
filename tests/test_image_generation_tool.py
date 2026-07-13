from types import SimpleNamespace

from core.llm_tools.image_generation import BigBananaImageGenerationTool
from core.schemas import GenerationResult, ImageResource


def build_result(count: int) -> GenerationResult:
    return GenerationResult(
        images=[
            ImageResource("image/png", f"image-{index}".encode())
            for index in range(count)
        ],
        urls=[f"https://example.com/{index}.png" for index in range(count)],
    )


def test_llm_image_truncation_is_disabled_by_default() -> None:
    plugin = SimpleNamespace(
        llm_tools_config=SimpleNamespace(llm_tool_truncate_images=False)
    )
    result = build_result(3)

    BigBananaImageGenerationTool._truncate_excess_images(plugin, {"n": 1}, result)

    assert len(result.images) == 3
    assert len(result.urls) == 3


def test_llm_image_result_is_truncated_to_requested_count() -> None:
    plugin = SimpleNamespace(
        llm_tools_config=SimpleNamespace(llm_tool_truncate_images=True)
    )
    result = build_result(4)

    BigBananaImageGenerationTool._truncate_excess_images(plugin, {"n": 2}, result)

    assert len(result.images) == 2
    assert len(result.urls) == 2


def test_llm_image_truncation_defaults_to_one_image() -> None:
    plugin = SimpleNamespace(
        llm_tools_config=SimpleNamespace(llm_tool_truncate_images=True)
    )
    result = build_result(3)

    BigBananaImageGenerationTool._truncate_excess_images(plugin, {}, result)

    assert len(result.images) == 1
    assert len(result.urls) == 1
