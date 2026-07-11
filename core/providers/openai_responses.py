import json
from typing import Any

from astrbot.api import logger

from .standard import StandardProvider


class OpenAIResponsesProvider(StandardProvider):
    """OpenAI Responses API 图片生成工具提供商。"""

    provider_type = "OpenAI_Responses"

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """构建 Responses API 请求头。"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def _build_body_context(self) -> dict:
        """构建 Responses API 请求体。"""
        if self._body_context_cache is not None:
            return self._body_context_cache

        context: dict[str, Any] = {
            "model": self.provider_config.model,
            "input": self._build_input(),
            "tools": [self._build_image_tool()],
            "tool_choice": {"type": "image_generation"},
        }
        if self.provider_config.stream:
            context["stream"] = True

        self._body_context_cache = context
        return context

    def _build_input(self) -> str | list[dict[str, Any]]:
        """构建 Responses API 输入内容。"""
        prompt = self.params.get("prompt", "draw a picture")
        if not self.image_list:
            return prompt

        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for image in self.image_list:
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{image.mime};base64,{image.base64}",
                }
            )
        return [{"role": "user", "content": content}]

    def _build_image_tool(self) -> dict:
        """构建 image_generation 工具参数。"""
        tool: dict[str, Any] = {"type": "image_generation"}
        size = self.determine_openai_size()
        if size != "default":
            tool["size"] = size
        moderation = self.params.get(
            "moderation", self.plugin.params_config.moderation
        )
        if moderation:
            tool["moderation"] = moderation
        if self.provider_config.stream:
            tool["partial_images"] = self.params.get(
                "partial_images", self.plugin.params_config.partial_images
            )
        return tool

    def _extract_result(
        self,
        result: dict,
    ) -> tuple[list[str], str | None]:
        """解析 Responses API 响应中的 image_generation_call 结果。"""
        image_sources: list[str] = []
        reason = None
        try:
            for output in result.get("output", []):
                if output.get("type") == "image_generation_call":
                    b64_data = output.get("result")
                    if b64_data:
                        image_sources.append(b64_data)

            output_text = result.get("output_text")
            if output_text:
                self.text_response_parts.append(output_text)
        except (AttributeError, TypeError) as e:
            logger.error(f"[BIG BANANA] 响应数据解析错误: {e}")
        return image_sources, reason

    def _extract_stream_result(
        self,
        stream_text: str,
    ) -> tuple[list[str], str | None]:
        """解析 Responses API SSE 响应中的图片结果。"""
        image_sources: list[str] = []
        reason = None
        for line in stream_text.splitlines():
            if not line.startswith("data: "):
                continue
            line_data = line[len("data: ") :].strip()
            if line_data == "[DONE]":
                continue
            try:
                event = json.loads(line_data)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            if event.get("type") != "response.completed":
                continue
            response = event.get("response")
            if not isinstance(response, dict):
                continue

            event_image_sources, event_reason = self._extract_result(response)
            image_sources.extend(event_image_sources)
            if event_reason:
                reason = event_reason
        return image_sources, reason

    def _build_api_url(self) -> str:
        """构建 Responses API 接口地址。"""
        url = (
            (self.provider_config.base_url or "https://api.openai.com/v1")
            .strip()
            .rstrip("/")
        )
        if url.endswith("/responses"):
            return url
        if url.endswith("/v1"):
            return f"{url}/responses"
        return f"{url}/v1/responses"
