
from .core import AbstractFS, open_fs
from .local import LocalFS

__all__ = ["AbstractFS", "open_fs", "LocalFS"]
__version__ = "0.1.0"
