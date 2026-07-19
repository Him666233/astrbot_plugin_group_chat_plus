"""AstrBot API 兼容聚合文件。

本文件只负责拼接各个原子分块并统一导出，不直接承载具体兼容逻辑。
"""

from .blocks.internal_loaders import *
from .blocks.internal_loaders import __all__ as _internal_loader_exports
from .blocks.public_api import *
from .blocks.public_api import __all__ as _public_api_exports

__all__ = [*_public_api_exports, *_internal_loader_exports]
