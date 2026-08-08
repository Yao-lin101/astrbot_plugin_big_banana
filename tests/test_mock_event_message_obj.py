from types import SimpleNamespace
from unittest.mock import Mock

import astrbot.api.message_components as Comp

from core.commands.drawing.handler import DrawingCommandHandler
from core.schemas import GenerationResult, ImageResource
from core.utils import (
    QuoteReplyMode,
    build_image_component,
    build_reply_component,
    get_message_id,
)


def test_get_message_id_and_build_reply_with_valid_event() -> None:
    event = SimpleNamespace(message_obj=SimpleNamespace(message_id="msg_123"))
    assert get_message_id(event) == "msg_123"
    reply = build_reply_component(event)
    assert reply is not None
    assert reply.id == "msg_123"


def test_get_message_id_and_build_reply_without_message_obj() -> None:
    event = SimpleNamespace()
    assert get_message_id(event) is None
    assert build_reply_component(event) is None


def test_get_message_id_with_non_string_message_id() -> None:
    event = SimpleNamespace(message_obj=SimpleNamespace(message_id=12345))
    assert get_message_id(event) == "12345"


def test_get_message_id_with_zero_id() -> None:
    event = SimpleNamespace(message_obj=SimpleNamespace(message_id=0))
    assert get_message_id(event) == "0"
    reply = build_reply_component(event)
    assert reply is not None
    assert reply.id == "0"


def test_get_message_id_and_build_reply_with_mock_raising_attribute_error() -> None:
    # 模拟 Mock 对象，访问 message_obj 显式抛出 AttributeError
    mock_event = Mock(spec=["unified_msg_origin", "platform_meta"])
    assert get_message_id(mock_event) is None
    assert build_reply_component(mock_event) is None


def test_build_result_message_chain_without_message_obj() -> None:
    handler = DrawingCommandHandler.__new__(DrawingCommandHandler)

    mock_event = Mock(spec=["unified_msg_origin", "platform_meta"])
    mock_event.platform_meta = SimpleNamespace(name="qq")

    result = GenerationResult(images=[SimpleNamespace(bytes=b"dummy", base64=None)])
    chain = handler._build_result_message_chain(mock_event, result)

    # 校验结果消息链中不包含 Comp.Reply
    assert not any(isinstance(comp, Comp.Reply) for comp in chain)


def test_build_image_component_http_url() -> None:
    img = SimpleNamespace(url="http://example.com/test.png", base64=None)
    comp = build_image_component(img)
    assert isinstance(comp, Comp.Image)
    assert comp.file == "http://example.com/test.png"


def test_build_image_component_file_url() -> None:
    img = SimpleNamespace(url="file:///tmp/test.png", base64=None)
    comp = build_image_component(img)
    assert isinstance(comp, Comp.Image)
    assert "tmp/test.png" in comp.file


def test_build_image_component_base64_image() -> None:
    img = SimpleNamespace(url=None, base64="b64data")
    comp = build_image_component(img)
    assert isinstance(comp, Comp.Image)
    assert comp.file == "base64://b64data"


def test_build_image_component_uses_fallback_when_no_image_or_base64() -> None:
    comp = build_image_component(None, fallback_url="https://example.com/fallback.png")
    assert isinstance(comp, Comp.Image)
    assert comp.file == "https://example.com/fallback.png"


def test_build_image_component_without_url_or_base64_or_fallback() -> None:
    img = SimpleNamespace(url=None, base64=None)
    comp = build_image_component(img)
    assert isinstance(comp, Comp.Plain)
    assert "图片无法加载" in comp.text


def test_quote_reply_mode_options() -> None:
    event = SimpleNamespace(message_obj=SimpleNamespace(message_id="msg_123"))

    # both
    p_both = SimpleNamespace(preference_config=SimpleNamespace(quote_reply_mode="both"))
    assert build_reply_component(event, is_command=True, plugin=p_both) is not None
    assert build_reply_component(event, is_command=False, plugin=p_both) is not None

    # command_only
    p_cmd = SimpleNamespace(preference_config=SimpleNamespace(quote_reply_mode="command_only"))
    assert build_reply_component(event, is_command=True, plugin=p_cmd) is not None
    assert build_reply_component(event, is_command=False, plugin=p_cmd) is None

    # tool_only
    p_tool = SimpleNamespace(preference_config=SimpleNamespace(quote_reply_mode="tool_only"))
    assert build_reply_component(event, is_command=True, plugin=p_tool) is None
    assert build_reply_component(event, is_command=False, plugin=p_tool) is not None

    # none
    p_none = SimpleNamespace(preference_config=SimpleNamespace(quote_reply_mode="none"))
    assert build_reply_component(event, is_command=True, plugin=p_none) is None
    assert build_reply_component(event, is_command=False, plugin=p_none) is None




