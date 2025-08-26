
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlparse

import paramiko

from .core import AbstractFS, StrOrPath

@dataclass
class _ConnInfo:
    host: str
    port: int
    username: str | None
    path: str

class SFTPFS(AbstractFS):
    """SFTP-backed filesystem."""

    def __init__(self, client: paramiko.SFTPClient, base: str = "/") -> None:
        self.client = client
        self.base = base.rstrip("/")

    @classmethod
    def from_uri(cls, uri: str) -> "SFTPFS":
        parsed = urlparse(uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 22
        user = parsed.username
        base = parsed.path or "/"
        transport = paramiko.Transport((host, port))
        # Authentication will rely on agent or key files; for passwords, users
        # should create their own connected client and pass it in.
        transport.connect(username=user)
        client = paramiko.SFTPClient.from_transport(transport)
        return cls(client, base=base)

    def _p(self, path: StrOrPath) -> str:
        path = str(path).lstrip("/")
        return f"{self.base}/{path}" if path else self.base

    def open(self, path: StrOrPath, mode: str = "rb") -> io.IOBase:
        return self.client.open(self._p(path), mode)

    def read_bytes(self, path: StrOrPath) -> bytes:
        with self.open(path, "rb") as f:
            return f.read()

    def write_bytes(self, path: StrOrPath, data: bytes) -> None:
        p = self._p(path)
        # Ensure directory exists
        dirp = "/".join(p.split("/")[:-1])
        try:
            self.client.stat(dirp)
        except IOError:
            self.mkdirs(dirp, exist_ok=True)
        with self.open(path, "wb") as f:
            f.write(data)

    def exists(self, path: StrOrPath) -> bool:
        try:
            self.client.stat(self._p(path))
            return True
        except IOError:
            return False

    def ls(self, path: StrOrPath = ".") -> List[str]:
        p = self._p(path)
        return [e.filename for e in self.client.listdir_attr(p)]

    def rm(self, path: StrOrPath, recursive: bool = False) -> None:
        p = self._p(path)
        try:
            self.client.remove(p)
        except IOError:
            # directory
            for name in self.ls(path):
                self.rm(f"{path}/{name}", recursive=True)
            self.client.rmdir(p)

    def mkdirs(self, path: StrOrPath, exist_ok: bool = True) -> None:
        parts = str(path).strip("/").split("/")
        cur = self.base
        for part in parts:
            cur = f"{cur}/{part}"
            try:
                self.client.mkdir(cur)
            except IOError:
                if not exist_ok:
                    raise

    def mv(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        s, d = self._p(src), self._p(dst)
        if not overwrite and self.exists(dst):
            raise FileExistsError(dst)
        if overwrite and self.exists(dst):
            self.rm(dst)
        self.client.rename(s, d)

    def cp(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        data = self.read_bytes(src)
        self.write_bytes(dst, data)
