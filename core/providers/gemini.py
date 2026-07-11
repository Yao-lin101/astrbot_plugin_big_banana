import json
from typing import Any

from astrbot.api import logger

from .standard import StandardProvider
from .utils import parse_response_modalities


class GeminiProvider(StandardProvider):
    """Gemini 提供商"""

    provider_type = "Gemini"

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """构建 Gemini 请求头"""
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

    def _build_body_context(self) -> dict:
        """构建 Gemini 图片生成请求体。"""
        # 读取缓存
        if self._body_context_cache is not None:
            return self._body_context_cache

        parts = []
        # 处理图片内容部分
        for image in self.image_list:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": image.mime,
                        "data": image.base64,
                    }
                }
            )

        # 处理响应内容的类型
        response_modalities = parse_response_modalities(
            self.provider_config.raw_config.get("response_modalities", '["IMAGE"]')
        )

        # 构建请求上下文
        context: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": self.params.get("prompt", "draw a picture")},
                        *parts,
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 1,
                "topP": 0.95,
                "maxOutputTokens": 32768,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "OFF",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "OFF",
                },
            ],
        }

        if response_modalities:
            context["generationConfig"]["responseModalities"] = response_modalities

        image_config = {}
        # 处理图片宽高比参数
        aspect_ratio = self.params.get(
            "aspect_ratio", self.plugin.params_config.aspect_ratio
        )
        if aspect_ratio != "default":
            image_config["aspectRatio"] = aspect_ratio

        # 以下参数仅 Gemini-3 模型有效
        if "gemini-3" in self.provider_config.model.lower():
            # 处理工具类
            if self.params.get(
                "google_search", self.plugin.params_config.google_search
            ):
                context["tools"] = [{"google_search": {}}]
            # 处理图片分辨率参数
            image_size = self.params.get(
                "image_size", self.plugin.params_config.image_size
            )
            image_config["imageSize"] = image_size

        if image_config:
            context["generationConfig"]["imageConfig"] = image_config

        self._body_context_cache = context
        return context

    def _extract_result(
        self,
        result: dict,
    ) -> tuple[list[str], str | None]:
        """解析 Gemini 响应中的 inlineData 图片。"""
        image_sources: list[str] = []
        text_parts: list[str] = []
        reason = None
        try:
            # 检查错误
            block_reason = result.get("promptFeedback", {}).get("blockReason")
            # 即便有错误，仍然需要继续寻找图片，避免误判
            if block_reason:
                reason = f"请求被内容安全系统拦截，原因：{block_reason}"
            # 解析内容
            for item in result.get("candidates", []):
                # 这个不一定是错误，仅作回退时查找错误原因
                candidate_reason = item.get("finishMessage") or item.get("finishReason")
                # 不覆盖更明显的错误原因
                if candidate_reason and candidate_reason != "STOP" and reason is None:
                    reason = candidate_reason
                # 解析图片
                for part in item.get("content", {}).get("parts", []):
                    text = part.get("text")
                    if text:
                        text_parts.append(text)
                    data_base64 = part.get("inlineData", {}).get("data")
                    if data_base64:
                        image_sources.append(data_base64)
        except (AttributeError, TypeError) as e:
            logger.error(f"[BIG BANANA] 响应数据解析错误: {e}")

        if text_parts:
            self.text_response_parts.extend(text_parts)
        return image_sources, reason

    def _extract_stream_result(self, stream_text: str) -> tuple[list[str], str | None]:
        """从 Gemini SSE 文本中解析图片和失败原因。"""
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
        """构建 Gemini generateContent 接口地址。"""
        action = (
            "streamGenerateContent?alt=sse"
            if self.provider_config.stream
            else "generateContent"
        )
        url = (
            (
                self.provider_config.base_url
                or "https://generativelanguage.googleapis.com"
            )
            .strip()
            .rstrip("/")
        )
        model = self.provider_config.model
        last_segment = url.rsplit("/", 1)[-1]
        if (
            ":generateContent" in last_segment
            or ":streamGenerateContent" in last_segment
        ):
            return f"{url.rsplit(':', 1)[0]}:{action}"
        if url.endswith(f"/models/{model}"):
            return f"{url}:{action}"
        if url.endswith("/models"):
            return f"{url}/{model}:{action}"
        if url.endswith(("/v1", "/v1beta")):
            return f"{url}/models/{model}:{action}"
        return f"{url}/v1beta/models/{model}:{action}"
