import json
import re
from io import BytesIO

from curl_cffi.requests.exceptions import Timeout
from PIL import Image

from astrbot.api import logger

from .base import BaseProvider
from .data import ProviderConfig

# Regex to extract base64 encoded images in markdown format from chat content
_IMG_RE = re.compile(r"!\[[^\]]*\]\((data:image/[^;)]+;base64,[^)]+)\)")


class NewAPIImagesProvider(BaseProvider):
    """Provider for drawing services exposed via NewAPI chat/completions endpoint."""

    api_type: str = "NewAPI_Images"

    async def _call_api(
        self,
        provider_config: ProviderConfig,
        api_key: str,
        image_b64_list: list[tuple[str, str]],
        params: dict,
    ) -> tuple[list[tuple[str, str]] | None, int | None, str | None]:
        """Perform NewAPI image generation request.

        Args:
            provider_config: The provider configuration.
            api_key: API key for authentication.
            image_b64_list: List of base64 input images.
            params: Drawing configuration parameters.

        Returns:
            A tuple of (images_result, status_code, error_message).
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # Determine target size
        size = [832, 1216]  # default portrait size
        size_val = params.get("size")
        if isinstance(size_val, str) and "x" in size_val:
            try:
                w, h = map(int, size_val.split("x"))
                size = [w, h]
            except Exception as e:
                logger.warning(
                    f"[BIG BANANA] Failed to parse size parameter '{size_val}': {e}"
                )
        else:
            # Fall back to aspect ratio mapping
            aspect_ratio = params.get(
                "aspect_ratio", self.def_prompt_config.aspect_ratio
            )
            if aspect_ratio != "default":
                # Vertical aspect ratios mapping
                if aspect_ratio in {"2:3", "3:4", "4:5", "9:16"}:
                    size = [832, 1216]
                # Horizontal aspect ratios mapping
                elif aspect_ratio in {"3:2", "4:3", "5:4", "16:9", "21:9"}:
                    size = [1216, 832]
                # Square aspect ratio mapping
                elif aspect_ratio == "1:1":
                    size = [1024, 1024]

        # Base parameters
        draw_params = {
            "prompt": params.get("prompt", "1girl"),
            "size": size,
        }

        # Optional base parameters
        if "negative_prompt" in params:
            draw_params["negative_prompt"] = params["negative_prompt"]
        if "steps" in params:
            try:
                draw_params["steps"] = min(int(params["steps"]), 28)
            except ValueError:
                pass
        if "sampler" in params:
            draw_params["sampler"] = params["sampler"]
        if "seed" in params:
            try:
                draw_params["seed"] = int(params["seed"])
            except ValueError:
                pass
        if "image_format" in params:
            draw_params["image_format"] = params["image_format"]
        if "variety_boost" in params:
            draw_params["variety_boost"] = bool(params["variety_boost"])
        if "cfg_rescale" in params:
            try:
                draw_params["cfg_rescale"] = float(params["cfg_rescale"])
            except ValueError:
                pass
        if "noise_schedule" in params:
            draw_params["noise_schedule"] = params["noise_schedule"]

        # Map reference images based on ref_type
        ref_type = params.get("ref_type", "i2i")
        if image_b64_list:
            if ref_type == "character":
                # Precise character reference, up to 1 image
                mime, b64 = image_b64_list[0]
                draw_params["character_references"] = [
                    {
                        "image": f"data:{mime};base64,{b64}",
                        "type": "character&style",
                        "fidelity": 1.0,
                        "strength": 1.0,
                    }
                ]
            elif ref_type in {"vibe", "controlnet"}:
                # Vibe transfer, up to 4 images
                images = []
                for mime, b64 in image_b64_list[:4]:
                    images.append(
                        {
                            "image": f"data:{mime};base64,{b64}",
                            "info_extracted": 0.7,
                            "strength": 0.6,
                        }
                    )
                draw_params["controlnet"] = {"strength": 1.0, "images": images}
            elif ref_type == "i2i":
                # Image to Image, 1 image, requiring size matching
                mime, b64 = image_b64_list[0]
                try:
                    import base64 as b64_lib

                    raw_bytes = b64_lib.b64decode(b64)
                    with Image.open(BytesIO(raw_bytes)) as img:
                        if img.size != tuple(size):
                            img_resized = img.convert("RGB").resize(
                                tuple(size), Image.Resampling.LANCZOS
                            )
                            buf = BytesIO()
                            img_resized.save(buf, format="PNG")
                            b64 = b64_lib.b64encode(buf.getvalue()).decode("utf-8")
                            mime = "image/png"
                except Exception as resize_err:
                    logger.warning(
                        f"[BIG BANANA] Failed to auto-resize i2i image: {resize_err}"
                    )
                draw_params["i2i"] = {
                    "image": f"data:{mime};base64,{b64}",
                    "strength": 0.7,
                    "noise": 0.0,
                }
            elif ref_type == "inpaint":
                # Inpaint, requires image and mask (defaults to white mask if missing)
                mime_img, b64_img = image_b64_list[0]
                b64_mask = ""
                mime_mask = "image/png"
                if len(image_b64_list) > 1:
                    mime_mask, b64_mask = image_b64_list[1]
                else:
                    try:
                        import base64 as b64_lib

                        mask_img = Image.new("L", tuple(size), 255)
                        buf = BytesIO()
                        mask_img.save(buf, format="PNG")
                        b64_mask = b64_lib.b64encode(buf.getvalue()).decode("utf-8")
                    except Exception as mask_err:
                        logger.warning(
                            f"[BIG BANANA] Failed to create default mask: {mask_err}"
                        )

                # Resize image and mask to match size
                try:
                    import base64 as b64_lib

                    raw_bytes_img = b64_lib.b64decode(b64_img)
                    with Image.open(BytesIO(raw_bytes_img)) as img:
                        if img.size != tuple(size):
                            img_resized = img.convert("RGB").resize(
                                tuple(size), Image.Resampling.LANCZOS
                            )
                            buf = BytesIO()
                            img_resized.save(buf, format="PNG")
                            b64_img = b64_lib.b64encode(buf.getvalue()).decode("utf-8")
                            mime_img = "image/png"

                    if b64_mask:
                        raw_bytes_mask = b64_lib.b64decode(b64_mask)
                        with Image.open(BytesIO(raw_bytes_mask)) as img_m:
                            if img_m.size != tuple(size):
                                img_m_resized = img_m.convert("L").resize(
                                    tuple(size), Image.Resampling.LANCZOS
                                )
                                buf = BytesIO()
                                img_m_resized.save(buf, format="PNG")
                                b64_mask = b64_lib.b64encode(buf.getvalue()).decode(
                                    "utf-8"
                                )
                                mime_mask = "image/png"
                except Exception as resize_err:
                    logger.warning(
                        f"[BIG BANANA] Failed to auto-resize inpaint: {resize_err}"
                    )

                draw_params["inpaint"] = {
                    "image": f"data:{mime_img};base64,{b64_img}",
                    "mask": f"data:{mime_mask};base64,{b64_mask}",
                    "strength": 1.0,
                }

        # Build outer request payload
        request_body = {
            "model": provider_config.model,
            "messages": [
                {"role": "user", "content": json.dumps(draw_params)},
            ],
            "stream": False,
            "max_tokens": 100000,
        }

        try:
            response = await self.session.post(
                url=provider_config.api_url,
                headers=headers,
                json=request_body,
                timeout=self.def_common_config.timeout,
                proxy=self.def_common_config.proxy,
            )

            # Check response status
            if response.status_code == 200:
                result = response.json()
                choices = result.get("choices", [])
                if not choices:
                    return None, 200, "响应中未包含 choices 列表"

                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    return None, 200, "响应内容为空"

                images = _IMG_RE.findall(content)
                if not images:
                    logger.warning(
                        f"[BIG BANANA] Request succeeded but no images were found. Content: {content[:1000]}"
                    )
                    return None, 200, "响应中未提取到图片数据"

                b64_images = []
                for img_src in images:
                    if img_src.startswith("data:image/"):
                        header, base64_data = img_src.split(",", 1)
                        mime = header.split(";")[0].replace("data:", "")
                        b64_images.append((mime, base64_data))

                if not b64_images:
                    return None, 200, "解析图片 base64 数据失败"

                return b64_images, 200, None
            else:
                logger.error(
                    f"[BIG BANANA] NewAPI_Images generation failed, status code: {response.status_code}, content: {response.text[:1024]}"
                )
                err_msg = ""
                try:
                    err_data = response.json()
                    error_obj = err_data.get("error", {})
                    if isinstance(error_obj, dict):
                        err_msg = error_obj.get("message") or ""
                except Exception:
                    pass

                return (
                    None,
                    response.status_code,
                    err_msg or f"图片生成失败: 状态码 {response.status_code}",
                )
        except Timeout as e:
            logger.error(f"[BIG BANANA] Network request timeout: {e}")
            return None, 408, "图片生成失败：响应超时"
        except Exception as e:
            logger.error(f"[BIG BANANA] Request error: {e}", exc_info=True)
            return None, None, f"图片生成失败：程序异常 {e}"

    async def _call_stream_api(
        self,
        provider_config: ProviderConfig,
        api_key: str,
        image_b64_list: list[tuple[str, str]],
        params: dict,
    ) -> tuple[list[tuple[str, str]] | None, int | None, str | None]:
        """Call streaming API, falls back to non-streaming.

        Args:
            provider_config: Provider configuration.
            api_key: API Key string.
            image_b64_list: List of base64 images.
            params: Parameters for drawing.

        Returns:
            Tuple of image list, status code, and error message.
        """
        logger.warning(
            "[BIG BANANA] NewAPI_Images 暂不支持流式响应，将自动回退为非流式请求"
        )
        return await self._call_api(
            provider_config=provider_config,
            api_key=api_key,
            image_b64_list=image_b64_list,
            params=params,
        )
