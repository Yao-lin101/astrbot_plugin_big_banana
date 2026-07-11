from __future__ import annotations

from typing import TYPE_CHECKING

from astrbot.api import logger

from ..schemas import GenerationResult, ImageResource
from .saver import ImageSaver

if TYPE_CHECKING:
    from ...main import BigBanana


class DrawingPipeline:
    """根据已准备好的图片列表执行图片生成和结果收尾。"""

    def __init__(self, plugin: BigBanana) -> None:
        """初始化绘图组件。"""
        self.plugin = plugin
        self.image_saver = ImageSaver()

    async def run(
        self, params: dict, image_list: list[ImageResource]
    ) -> GenerationResult:
        """负责生成、上传/保存和错误收尾"""
        # 调度底层提供商生成图片
        dispatch_result = await self.plugin.dispatcher.dispatch(
            params=params, image_list=image_list
        )

        # 检查错误
        if not dispatch_result.images:
            err = dispatch_result.error_message
            if not err:
                err = "图片生成失败：响应中未包含图片数据"
                logger.error(err)
            return GenerationResult(error_message=err)

        # URL 模式
        if params.get("url", self.plugin.params_config.url):
            uploaded_urls: list[str | None] = [None] * len(dispatch_result.images)
            if self.plugin.image_hoster.is_enabled():
                uploaded_urls = await self.plugin.image_hoster.upload_images(
                    dispatch_result.images
                )

            # 每张图片优先使用图床 URL；上传失败时使用提供商原始 URL。
            result_urls: list[str] = []
            for image, uploaded_url in zip(dispatch_result.images, uploaded_urls):
                if uploaded_url:
                    result_urls.append(uploaded_url)
                elif isinstance(image.url, str) and image.url.startswith(
                    ("http://", "https://")
                ):
                    result_urls.append(image.url)

            if result_urls:
                if len(result_urls) < len(dispatch_result.images):
                    logger.warning(
                        f"[BIG BANANA] 共生成 {len(dispatch_result.images)} 张图片，"
                        f"其中 {len(result_urls)} 张取得了可用 URL，将返回现有结果"
                    )
                return GenerationResult(
                    images=dispatch_result.images,
                    urls=result_urls,
                )

            # 没有获得可用url，返回错误
            return GenerationResult(
                error_message=dispatch_result.error_message
                or "当前结果无法转换为可访问 URL，请检查图床配置或提供商返回的结果"
            )

        # 本地保存生成的图片
        if self.plugin.save_images.local_save:
            self.image_saver.save_images_to_local(
                dispatch_result.images, self.plugin.save_dir
            )

        return GenerationResult(images=dispatch_result.images)
