from dataclasses import dataclass, field

from .image import ImageResource


@dataclass(repr=False, slots=True)
class GenerationResult:
    """图片生成结果"""

    images: list[ImageResource] = field(default_factory=list)
    """ 生成的图片列表 """
    urls: list[str] = field(default_factory=list)
    """ 上传到图床的 URL 列表 """
    error_message: str | None = field(default=None, init=True)
    """ 错误消息 """
