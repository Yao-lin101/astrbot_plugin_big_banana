import json

from astrbot.api import logger

from .standard import StandardProvider
from .utils import extract_markdown_images


class OpenAIChatProvider(StandardProvider):
    """Chat Completions 图片生成提供商。"""

    provider_type = "OpenAI_Chat"

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """构建 Chat Completions 请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def _build_body_context(self) -> dict:
        """构建 Chat Completions 请求体"""
        # 读取缓存
        if self._body_context_cache is not None:
            return self._body_context_cache

        images_content = []
        for image in self.image_list:
            images_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image.mime};base64,{image.base64}"},
                }
            )
        context = {
            "model": self.provider_config.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.params.get("prompt", "draw a picture"),
                        },
                        *images_content,
                    ],
                }
            ],
            "stream": self.provider_config.stream,
        }

        # 写入缓存
        self._body_context_cache = context
        return context

    def _extract_result(
        self,
        result: dict,
    ) -> tuple[list[str], str | None]:
        """解析 Chat Completions 响应文本中的 Markdown 图片。"""
        image_sources: list[str] = []
        reason = None
        try:
            for item in result.get("choices", []):
                # 兼容非流式和流式响应，我还没见过一个base64拆几个消息块的
                message = item.get("message") or item.get("delta") or {}
                content = message.get("content")
                if isinstance(content, str):
                    base64_sources, markdown_image_urls = extract_markdown_images(
                        content
                    )
                    if not base64_sources and not markdown_image_urls:
                        self.text_response_parts.append(content)
                    image_sources.extend(base64_sources)
                    image_sources.extend(markdown_image_urls)
                finish_reason = item.get("finish_reason")
                if finish_reason and finish_reason.lower() != "stop":
                    reason = finish_reason
        except (AttributeError, TypeError) as e:
            logger.error(f"[BIG BANANA] 响应数据解析错误: {e}")
        return image_sources, reason

    def _extract_stream_result(
        self,
        stream_text: str,
    ) -> tuple[list[str], str | None]:
        """解析 Chat Completions SSE 响应文本中的 Markdown 图片。"""
        image_sources: list[str] = []
        reason = None
        for line in stream_text.splitlines():
            if not line.startswith("data: "):
                continue
            line_data = line[len("data: ") :].strip()
            if line_data == "[DONE]":
                # 许多接口并不严格保证[DONE]一定在消息块的最后，所以不break
                continue
            try:
                event = json.loads(line_data)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                event_image_sources, event_reason = self._extract_result(event)
                image_sources.extend(event_image_sources)
                if event_reason:
                    reason = event_reason
        return image_sources, reason

    def _build_api_url(self) -> str:
        """构建 Chat Completions 接口地址"""
        url = (
            (self.provider_config.base_url or "https://api.openai.com/v1")
            .strip()
            .rstrip("/")
        )
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/chat"):
            return f"{url}/completions"
        if url.endswith("/v1"):
            return f"{url}/chat/completions"
        return f"{url}/v1/chat/completions"
