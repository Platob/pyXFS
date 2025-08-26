
from __future__ import annotations

import abc
import io
import os
from pathlib import Path
from typing import Iterable, List, Optional, Union
from urllib.parse import urlparse

StrOrPath = Union[str, os.PathLike]

class AbstractFS(abc.ABC):
    """Abstract filesystem interface.

    Implementations should be *path-rooted* at construction time (e.g. bucket or base directory).
    Paths passed to methods are relative to the root unless explicitly absolute within the backend.
    """

    @abc.abstractmethod
    def open(self, path: StrOrPath, mode: str = "rb") -> io.IOBase:
        ...

    @abc.abstractmethod
    def read_bytes(self, path: StrOrPath) -> bytes:
        ...

    @abc.abstractmethod
    def write_bytes(self, path: StrOrPath, data: bytes) -> None:
        ...

    def read_text(self, path: StrOrPath, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding)

    def write_text(self, path: StrOrPath, text: str, encoding: str = "utf-8") -> None:
        self.write_bytes(path, text.encode(encoding))

    @abc.abstractmethod
    def exists(self, path: StrOrPath) -> bool:
        ...

    @abc.abstractmethod
    def ls(self, path: StrOrPath = ".") -> List[str]:
        ...

    @abc.abstractmethod
    def rm(self, path: StrOrPath, recursive: bool = False) -> None:
        ...

    @abc.abstractmethod
    def mkdirs(self, path: StrOrPath, exist_ok: bool = True) -> None:
        ...

    @abc.abstractmethod
    def mv(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        ...

    @abc.abstractmethod
    def cp(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        ...


def open_fs(uri: str) -> AbstractFS:
    """Open a filesystem from a URI.

    Examples:
        file:///tmp/data
        s3://bucket/prefix
        sftp://user@host:22/path
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme or "file"
    if scheme in ("", "file"):
        base = parsed.path or "/"
        return LocalFS(base)
    if scheme == "s3":
        try:
            from .s3fs import S3FS  # type: ignore
        except Exception as e:
            raise ImportError("S3 support requires the 'boto3' dependency and the s3 extra: pip install 'pyxfs[s3]'") from e
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        return S3FS(bucket=bucket, prefix=prefix)
    if scheme == "sftp":
        try:
            from .sftpfs import SFTPFS  # type: ignore
        except Exception as e:
            raise ImportError("SFTP support requires the 'paramiko' dependency and the sftp extra: pip install 'pyxfs[sftp]'") from e
        return SFTPFS.from_uri(uri)
    raise ValueError(f"Unsupported URI scheme: {scheme!r}")
