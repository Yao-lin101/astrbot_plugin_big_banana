from dataclasses import dataclass, field

from .image import ImageResource
from .video import VideoResource


@dataclass(repr=False, slots=True)
class GenerationResult:
    """统一的图片或视频生成结果。"""

    images: list[ImageResource] = field(default_factory=list)
    """ 生成的图片列表 """
    videos: list[VideoResource] = field(default_factory=list)
    """ 生成的视频列表 """
    urls: list[str | None] = field(default_factory=list)
    """与图片顺序对齐的 URL 列表；无法取得 URL 的位置为 None。"""
    error_message: str | None = field(default=None, init=True)
    """ 错误消息 """
