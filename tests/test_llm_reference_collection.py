import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from core.drawing.collector import ImageCollector
from core.llm_tools.image_generation import BigBananaImageGenerationTool
from core.schemas import ImageResource


def build_event(platform_name: str = "aiocqhttp") -> SimpleNamespace:
    return SimpleNamespace(
        platform_meta=SimpleNamespace(name=platform_name),
        client=None,
        bot=None,
    )


def build_plugin(
    tmp_path: Path,
    *,
    refer_images: str | None = None,
    fetched_results: list[ImageResource | None] | None = None,
) -> SimpleNamespace:
    refer_images_dir = tmp_path / "refer_images"
    refer_images_dir.mkdir(exist_ok=True)
    return SimpleNamespace(
        params_config=SimpleNamespace(
            min_images=0,
            max_images=6,
            refer_images=refer_images,
        ),
        refer_images_dir=refer_images_dir,
        data_dir=tmp_path,
        avatar_map={},
        preference_config=SimpleNamespace(),
        llm_tools_config=SimpleNamespace(
            llm_tool_restrict_private_network=True,
        ),
        downloader=SimpleNamespace(
            fetch_images_keep_none=AsyncMock(return_value=fetched_results or [])
        ),
    )


def test_explicit_mixed_references_keep_the_original_order(tmp_path: Path) -> None:
    plugin = build_plugin(tmp_path)
    collector = ImageCollector(
        plugin=plugin,
        event=build_event(),
        params={},
        is_llm_tool=True,
    )

    asyncio.run(
        collector.add_explicit_references(
            ["https://example.com/first.png", "@123", "cached/third.png"]
        )
    )

    assert collector.get_final_urls() == [
        "https://example.com/first.png",
        ImageCollector.qq_avatar_url("123"),
        "cached/third.png",
    ]


def test_llm_collection_loads_default_refer_images_before_explicit_refs(
    tmp_path: Path,
) -> None:
    fixed_image = tmp_path / "refer_images" / "fixed.png"
    fixed_image.parent.mkdir()
    fixed_image.write_bytes(b"fixed")
    fetched = [
        ImageResource("image/png", b"fixed-image"),
        ImageResource("image/png", b"explicit-image"),
    ]
    plugin = build_plugin(
        tmp_path,
        refer_images="fixed.png",
        fetched_results=fetched,
    )

    images, _, error = asyncio.run(
        BigBananaImageGenerationTool()._collect_images(
            plugin,
            build_event(),
            {},
            ["https://example.com/explicit.png"],
        )
    )

    assert error is None
    assert images == fetched
    pending_urls = plugin.downloader.fetch_images_keep_none.await_args.args[0]
    assert pending_urls == [fixed_image.resolve(), "https://example.com/explicit.png"]


def test_llm_collection_does_not_build_avatar_numbering_notes(tmp_path: Path) -> None:
    plugin = build_plugin(
        tmp_path,
        fetched_results=[ImageResource("image/png", b"avatar-image")],
    )

    images, supplement_infos, error = asyncio.run(
        BigBananaImageGenerationTool()._collect_images(
            plugin,
            build_event(),
            {},
            ["@123"],
        )
    )

    assert error is None
    assert len(images) == 1
    assert supplement_infos == []


def test_llm_collection_identifies_the_failed_mixed_reference(
    tmp_path: Path,
) -> None:
    plugin = build_plugin(
        tmp_path,
        fetched_results=[
            ImageResource("image/png", b"first-image"),
            None,
            ImageResource("image/png", b"third-image"),
        ],
    )

    images, _, error = asyncio.run(
        BigBananaImageGenerationTool()._collect_images(
            plugin,
            build_event(),
            {"min_images": 1},
            [
                "https://example.com/first.png",
                "https://example.com/broken.png",
                "@123",
            ],
        )
    )

    assert images == []
    assert error is not None
    assert "参考图 https://example.com/broken.png 处理失败" in error
    assert "图片下载或读取失败" in error
    assert "https://example.com/first.png 处理失败" not in error
    assert "@123 处理失败" not in error


def test_llm_collection_identifies_an_unresolvable_avatar(tmp_path: Path) -> None:
    plugin = build_plugin(tmp_path)

    images, _, error = asyncio.run(
        BigBananaImageGenerationTool()._collect_images(
            plugin,
            build_event("unsupported"),
            {},
            ["https://example.com/usable.png", "@unknown-user"],
        )
    )

    assert images == []
    assert error is not None
    assert "参考图 @unknown-user 处理失败" in error
    assert "无法获取该用户头像" in error
    plugin.downloader.fetch_images_keep_none.assert_not_awaited()


def test_refer_images_config_hint_covers_commands_and_llm_tools() -> None:
    schema_path = Path(__file__).parents[1] / "_conf_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    hint = schema["params_config"]["items"]["refer_images"]["hint"]
    assert "命令调用" in hint
    assert "LLM 图片/视频工具调用" in hint
