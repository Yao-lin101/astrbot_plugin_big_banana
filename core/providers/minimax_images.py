import json

from ..schemas import ImageResource
from .standard import StandardProvider


class MiniMaxImagesProvider(StandardProvider):
    """MiniMax 图片生成提供商。"""

    provider_type = "MiniMax_Images"

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """构建 MiniMax Images 请求头。"""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _build_body_context(self) -> dict:
        """构建 MiniMax image_generation 请求体。"""
        if self._body_context_cache is not None:
            return self._body_context_cache

        context = {
            "model": self.provider_config.model,
            "prompt": self.params.get("prompt", "draw a picture"),
            "response_format": "base64",
            "n": self.params.get("n", self.plugin.params_config.n),
        }

        aspect_ratio = self.params.get(
            "aspect_ratio", self.plugin.params_config.aspect_ratio
        )
        if aspect_ratio != "default":
            context["aspect_ratio"] = aspect_ratio

        if self.image_list:
            context["subject_reference"] = [
                {
                    "type": "character",
                    "image_file": self._build_reference_image(self.image_list[0]),
                }
            ]

        self._body_context_cache = context
        return context

    def _extract_result(
        self,
        result: dict,
    ) -> tuple[list[str], str | None]:
        """解析 MiniMax 响应中的图片来源。"""
        reason = self._extract_business_error(result)
        if reason:
            return [], reason

        image_sources: list[str] = []
        data = result.get("data", {})
        image_sources.extend(data.get("image_base64", []))
        image_sources.extend(data.get("image_urls", []))
        return image_sources, None

    def _extract_stream_result(
        self,
        stream_text: str,
    ) -> tuple[list[str], str | None]:
        """MiniMax image_generation 返回普通 JSON。"""
        return self._extract_result(json.loads(stream_text))

    def _build_api_url(self) -> str:
        """构建 MiniMax image_generation 接口地址。"""
        url = (
            (self.provider_config.base_url or "https://api.minimax.io/v1")
            .strip()
            .rstrip("/")
        )
        if url.endswith("/image_generation"):
            return url
        if url.endswith("/v1"):
            return f"{url}/image_generation"
        return f"{url}/v1/image_generation"

    def _build_reference_image(self, image: ImageResource) -> str:
        """构建 MiniMax subject_reference 图片字段。"""
        if isinstance(image.url, str) and image.url.startswith(("http://", "https://")):
            return image.url
        return image.to_data_url()

    def _extract_business_error(self, result: dict) -> str | None:
        """解析 MiniMax 200 响应中的业务错误。"""
        base_resp = result.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code == 0:
            return None
        status_msg = base_resp.get("status_msg", "未知原因")
        return f"{status_code}: {status_msg}"
