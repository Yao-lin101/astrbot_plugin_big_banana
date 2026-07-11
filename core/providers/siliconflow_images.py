import json

from astrbot.api import logger

from ..schemas import ImageResource
from .standard import StandardProvider


class SiliconFlowImagesProvider(StandardProvider):
    """SiliconFlow 图片生成提供商。"""

    provider_type = "SiliconFlow_Images"

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """构建 SiliconFlow Images 请求头。"""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _build_body_context(self) -> dict:
        """构建 SiliconFlow 图片生成请求体。"""
        if self._body_context_cache is not None:
            return self._body_context_cache

        context = {
            "model": self.provider_config.model,
            "prompt": self.params.get("prompt", "draw a picture"),
        }

        image_size = self.params.get(
            "image_size", self.provider_config.raw_config.get("image_size", "")
        )
        if image_size and image_size != "default":
            context["image_size"] = image_size

        batch_size = self.params.get(
            "n", self.provider_config.raw_config.get("batch_size", 1)
        )
        if batch_size not in (None, ""):
            context["batch_size"] = int(batch_size)

        negative_prompt = self.params.get(
            "negative_prompt",
            self.provider_config.raw_config.get("negative_prompt", ""),
        )
        if negative_prompt:
            context["negative_prompt"] = negative_prompt.replace(",", " ")

        num_inference_steps = self.params.get(
            "num_inference_steps",
            self.provider_config.raw_config.get("num_inference_steps"),
        )
        if num_inference_steps not in (None, ""):
            context["num_inference_steps"] = int(num_inference_steps)

        guidance_scale = self.params.get(
            "guidance_scale",
            self.provider_config.raw_config.get("guidance_scale"),
        )
        if guidance_scale not in (None, ""):
            context["guidance_scale"] = float(guidance_scale)

        seed = self.params.get("seed", self.provider_config.raw_config.get("seed"))
        if seed not in (None, ""):
            context["seed"] = int(seed)

        if len(self.image_list) > 3:
            logger.warning("[BIG BANANA] SiliconFlow 图片接口最多传递 3 张参考图")
        for index, image in enumerate(self.image_list[:3], start=1):
            field_name = "image" if index == 1 else f"image{index}"
            context[field_name] = self._build_reference_image(image)

        self._body_context_cache = context
        return context

    def _extract_result(
        self,
        result: dict,
    ) -> tuple[list[str], str | None]:
        """解析 SiliconFlow 响应中的图片 URL。"""
        image_sources: list[str] = []
        for item in result.get("images", []):
            image_url = item.get("url")
            if image_url:
                image_sources.append(image_url)
        return image_sources, None

    def _extract_stream_result(
        self,
        stream_text: str,
    ) -> tuple[list[str], str | None]:
        """SiliconFlow 图片接口返回普通 JSON。"""
        return self._extract_result(json.loads(stream_text))

    def _build_api_url(self) -> str:
        """构建 SiliconFlow 图片生成接口地址。"""
        url = (
            (self.provider_config.base_url or "https://api.siliconflow.cn/v1")
            .strip()
            .rstrip("/")
        )
        if url.endswith("/images/generations"):
            return url
        if url.endswith("/images"):
            return f"{url}/generations"
        if url.endswith("/v1"):
            return f"{url}/images/generations"
        return f"{url}/v1/images/generations"

    def _build_reference_image(self, image: ImageResource) -> str:
        """构建 SiliconFlow 参考图字段。"""
        if isinstance(image.url, str) and image.url.startswith(("http://", "https://")):
            return image.url
        return image.to_data_url()
