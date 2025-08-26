
from __future__ import annotations

import io
import os
from typing import List, Optional

import boto3

from .core import AbstractFS, StrOrPath

class S3FS(AbstractFS):
    """S3-backed filesystem rooted at (bucket, optional prefix)."""

    def __init__(self, bucket: str, prefix: str = "", s3_client=None) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.s3 = s3_client or boto3.client("s3")

    def _k(self, path: StrOrPath) -> str:
        path = str(path).lstrip("/")
        return f"{self.prefix}/{path}".strip("/")

    def open(self, path: StrOrPath, mode: str = "rb") -> io.IOBase:
        if "r" in mode and "+" not in mode and "b" in mode:
            # Download to memory for simple reads
            data = self.read_bytes(path)
            return io.BytesIO(data)
        raise NotImplementedError("Use read_bytes/write_bytes for S3, or implement temporary file buffering.")

    def read_bytes(self, path: StrOrPath) -> bytes:
        resp = self.s3.get_object(Bucket=self.bucket, Key=self._k(path))
        return resp["Body"].read()

    def write_bytes(self, path: StrOrPath, data: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=self._k(path), Body=data)

    def exists(self, path: StrOrPath) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=self._k(path))
            return True
        except self.s3.exceptions.NoSuchKey:  # type: ignore[attr-defined]
            return False
        except Exception:
            # Could be a prefix; try list
            resp = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=self._k(path), MaxKeys=1)
            return resp.get("KeyCount", 0) > 0

    def ls(self, path: StrOrPath = ".") -> list[str]:
        prefix = self._k(path).rstrip("/") + "/"
        paginator = self.s3.get_paginator("list_objects_v2")
        result: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                result.append(cp["Prefix"].rstrip("/").split("/", 1)[-1])
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/") and key == prefix:
                    continue
                result.append(key[len(prefix):])
        return sorted(set([r for r in result if r]))

    def rm(self, path: StrOrPath, recursive: bool = False) -> None:
        key = self._k(path)
        if recursive:
            # delete all under prefix
            paginator = self.s3.get_paginator("list_objects_v2")
            to_delete = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=key.rstrip("/") + "/"):
                for obj in page.get("Contents", []):
                    to_delete.append({"Key": obj["Key"]})
                    if len(to_delete) == 1000:
                        self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": to_delete})
                        to_delete = []
            if to_delete:
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": to_delete})
        else:
            self.s3.delete_object(Bucket=self.bucket, Key=key)

    def mkdirs(self, path: StrOrPath, exist_ok: bool = True) -> None:
        # S3 is flat; emulate by creating a placeholder directory marker
        key = self._k(path).rstrip("/") + "/"
        if not exist_ok and self.exists(path):
            raise FileExistsError(path)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=b"")

    def mv(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        s, d = self._k(src), self._k(dst)
        if not overwrite and self.exists(dst):
            raise FileExistsError(dst)
        self.s3.copy_object(Bucket=self.bucket, CopySource={"Bucket": self.bucket, "Key": s}, Key=d)
        self.s3.delete_object(Bucket=self.bucket, Key=s)

    def cp(self, src: StrOrPath, dst: StrOrPath, overwrite: bool = False) -> None:
        s, d = self._k(src), self._k(dst)
        if not overwrite and self.exists(dst):
            raise FileExistsError(dst)
        self.s3.copy_object(Bucket=self.bucket, CopySource={"Bucket": self.bucket, "Key": s}, Key=d)
