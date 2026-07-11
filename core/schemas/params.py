from dataclasses import dataclass, field


@dataclass(repr=False, slots=True, init=False)
class ParamsConfig:
    """提示词中支持的参数，当缺失时可从这个类实例中获取默认参数"""

    min_images: int = 0
    """最小输入图片数量"""
    max_images: int = 6
    """最大输入图片数量"""
    aspect_ratio: str = "default"
    """图片宽高比"""
    image_size: str = "1K"
    """图片尺寸/分辨率"""
    google_search: bool = True
    """是否启用谷歌搜索功能"""
    refer_images: str | None = None
    """引用参考图片的文件名"""
    gather_mode: bool = False
    """是否启用收集模式"""
    url: bool = False
    """是否仅返回图片 URL，不直接发送图片"""
    moderation: str = "auto"
    """GPT 图像编辑模型的内容安全审核等级"""
    size: str = "default"
    """OpenAI 图片输出尺寸；default 表示由插件自动推导"""
    size_keyword_map: dict[tuple[str, ...], str] = field(default_factory=dict)
    """OpenAI 图片尺寸关键词映射"""
    n: int = 1
    """OpenAI 图片生成数量"""
    partial_images: int = 0
    """OpenAI 流式图片预览数量"""

    def __init__(
        self,
        min_images: int = 0,
        max_images: int = 6,
        aspect_ratio: str = "default",
        image_size: str = "1K",
        google_search: bool = True,
        refer_images: str | None = None,
        gather_mode: bool = False,
        url: bool = False,
        moderation: str = "auto",
        size: str = "default",
        size_keyword_map: list[str] | None = None,
        n: int = 1,
        partial_images: int = 0,
    ) -> None:
        self.min_images = min_images
        self.max_images = max_images
        self.aspect_ratio = aspect_ratio
        self.image_size = image_size
        self.google_search = google_search
        self.refer_images = refer_images
        self.gather_mode = gather_mode
        self.url = url
        self.moderation = moderation
        self.size = size
        self.size_keyword_map = self._parse_size_keyword_map(size_keyword_map or [])
        self.n = n
        self.partial_images = partial_images

    @staticmethod
    def _parse_size_keyword_map(raw: list[str]) -> dict[tuple[str, ...], str]:
        result: dict[tuple[str, ...], str] = {}
        for item in raw:
            keywords, sep, size = item.partition(":")
            parsed_keywords = tuple(
                keyword.strip() for keyword in keywords.split(",") if keyword.strip()
            )
            size = size.strip()
            if sep and parsed_keywords and size:
                result[parsed_keywords] = size
        return result
