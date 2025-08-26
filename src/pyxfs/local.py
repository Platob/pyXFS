
from __future__ import annotations

import io
import os
import shutil
from pathlib import Path
from typing import List, Union

from .core import AbstractFS, StrOrPath

class LocalFS(AbstractFS):
    """Filesystem backed by the local disk, rooted at a base directory."""

    def __init__(self, base: StrOrPath = "/") -> None:
        self.base = Path(base).expanduser().resolve()

    def _p(self, path: StrOrPath) -> Path:
        p = self.base.joinpath(Path(path))
        return p

    def open(self, path: StrOrPath, mode: str = "rb") -> io.IOBase:
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return open(p, mode)

    def read_bytes(self, path: StrOrPath) -> bytes:
        return self._p(path).read_bytes()

    def write_bytes(self, path: StrOrPath, data: bytes) -> None:
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def exists(self, path: StrOrPath) -> bool:
        return self._p(path).exists()

    def ls(self, path: StrOrPath = ".") -> List[str]:
        p = self._p(path)
        if not p.exists():
            return []
        return [str(child.relative_to(self.base)) for child in p.iterdir()]

    def rm(self, path: StrOrPath, recursive: bool = False) -> None:
        p = self._p(path)
        if recursive and p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink()
            except IsADirectoryError:
                p.rmdir()

    def mkdirs(self, path: StrOrPath, exist_ok: bool = True) -> None:
        self._p(path).mkdir(parents=True, exist_ok=exist_ok)

    def mv(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        s, d = self._p(src), self._p(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        if overwrite and d.exists():
            if d.is_dir():
                shutil.rmtree(d)
            else:
                d.unlink()
        shutil.move(str(s), str(d))

    def cp(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        s, d = self._p(src), self._p(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            if d.exists() and overwrite:
                shutil.rmtree(d)
            shutil.copytree(s, d, dirs_exist_ok=overwrite)
        else:
            if d.exists() and d.is_dir():
                d = d / s.name
            if d.exists() and not overwrite:
                raise FileExistsError(d)
            shutil.copy2(s, d)
