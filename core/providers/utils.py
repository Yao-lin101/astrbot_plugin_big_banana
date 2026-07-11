import re

from astrbot.api import logger

from ..schemas import ImageResource


def dedupe_images(images: list[ImageResource]) -> list[ImageResource]:
    """按图片字节内容去除重复结果。"""
    deduped: list[ImageResource] = []
    seen: set[bytes] = set()
    for image in images:
        if image.bytes in seen:
            continue
        seen.add(image.bytes)
        deduped.append(image)
    if len(images) != len(deduped):
        logger.debug(
            f"[BIG BANANA] 去除重复图片，从 {len(images)} 张减少到 {len(deduped)} 张"
        )
    return deduped


def extract_markdown_images(text: str) -> tuple[list[str], list[str]]:
    """从 Markdown 图片语法中提取 base64 和 URL 图片引用。"""
    base64_sources: list[str] = []
    image_urls: list[str] = []

    # 这里使用finditer遍历，避免search只会返回第一个匹配
    for match in re.finditer(r"!\[.*?\]\((.*?)\)", text):
        img_src = match.group(1).strip()
        # 移除Markdown允许的<..>格式
        if img_src.startswith("<") and img_src.endswith(">"):
            img_src = img_src[1:-1].strip()

        if img_src.startswith("data:image/"):  # base64格式
            base64_sources.append(img_src)
        else:  # url格式
            image_urls.append(img_src)
    return base64_sources, image_urls


def parse_response_modalities(raw: str | list[str]) -> list[str]:
    """解析 Gemini/Vertex 提供商配置中的响应模式。"""
    if isinstance(raw, list):
        return raw
    if raw == "无":
        return []
    return [
        item.strip().strip("\"'")
        for item in raw.strip("[]").split(",")
        if item.strip().strip("\"'")
    ]
