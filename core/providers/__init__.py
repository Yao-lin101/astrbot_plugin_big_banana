from importlib import import_module
from pkgutil import iter_modules

from .base import BaseProvider
from .standard import StandardProvider

for module in iter_modules(__path__):
    module_name = module.name
    # 跳过 内部模块 / 私有模块 以及 基类
    if module_name.startswith("_") or module_name in {
        "base",
        "standard",
        "utils",
    }:
        continue
    import_module(f"{__name__}.{module_name}")

__all__ = ["BaseProvider", "StandardProvider"]
