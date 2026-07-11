from dataclasses import dataclass


@dataclass(repr=False, slots=True)
class ImageHostingConfig:
    """图床上传配置"""

    enabled: bool = False
    """是否启用图床上传"""
    upload_url: str = ""
    """上传入口基础地址"""
    public_base_url: str = ""
    """公开访问基础地址"""
    auth_token: str = ""
    """图床鉴权令牌"""
    path_prefix: str = "big-banana"
    """上传路径前缀"""
