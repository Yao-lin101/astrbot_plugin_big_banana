from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from astrbot.api import logger

from ..client.downloader import handle_image

if TYPE_CHECKING:
    from ...main import BigBanana
    from ..schemas import ImageResource

# 上传前会先规范化格式；最终只允许这些 MIME 落到 R2。
_UPLOAD_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


class R2ImageHoster:
    """基于 Cloudflare Worker + R2 的图床上传器"""

    def __init__(self, plugin: BigBanana):
        self.plugin = plugin
        self.session = plugin.http_manager.get_aiohttp_session()
        self.config = plugin.image_hosting_config

    def is_enabled(self) -> bool:
        """检查图床上传所需配置是否完整。"""
        return bool(
            self.config.enabled
            and self.config.upload_url.strip()
            and self.config.public_base_url.strip()
            and self.config.auth_token.strip()
        )

    async def upload_image(self, image: ImageResource) -> str | None:
        """上传单张图片资源并返回公开 URL。"""
        normalized = handle_image(image.bytes, convert=True, allow_gif=True)
        if normalized is None:
            return None
        mime, data_bytes = normalized
        upload_key = self._build_upload_key(mime)
        if not await self._upload_bytes(upload_key, data_bytes, mime):
            return None
        return self._build_public_url(upload_key)

    async def upload_images(self, images: list[ImageResource]) -> list[str | None]:
        """批量上传图片资源，按图片顺序返回 URL 或空值。"""
        urls: list[str | None] = []
        for image in images:
            try:
                url = await self.upload_image(image)
            except Exception as e:
                logger.error(f"[BIG BANANA] 图床上传发生异常: {e}", exc_info=True)
                url = None
            urls.append(url)
        return urls

    def _build_upload_key(self, mime: str) -> str:
        """生成包含日期路径和随机文件名的 R2 对象键。"""
        ext = _UPLOAD_EXT_BY_MIME.get(mime, "jpg")
        filename = f"{uuid.uuid4().hex}.{ext}"

        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")
        prefix = self.config.path_prefix.strip().strip("/")
        if prefix:
            return f"{prefix}/{date_path}/{filename}"
        return f"{date_path}/{filename}"

    async def _upload_bytes(
        self, upload_key: str, image_bytes: bytes, mime: str
    ) -> bool:
        """把图片字节上传到 Cloudflare Worker/R2。"""
        upload_url = f"{self.config.upload_url.rstrip('/')}/{upload_key}"
        async with self.session.put(
            upload_url,
            data=image_bytes,
            headers={
                "X-Auth-Token": self.config.auth_token,
                "Content-Type": mime,
            },
        ) as response:
            if response.status < 200 or response.status >= 300:
                resp_text = await response.text()
                logger.error(
                    f"[BIG BANANA] 图床上传失败，状态码: {response.status}, 响应内容: {resp_text[:512]}"
                )
                return False
            return True

    def _build_public_url(self, upload_key: str) -> str:
        """根据对象键拼接公开访问地址。"""
        return f"{self.config.public_base_url.rstrip('/')}/{upload_key}"
