# src/pyxfs/path.py
from __future__ import annotations

import abc
import os.path
import posixpath
from dataclasses import dataclass
from typing import List, Any, Optional
from urllib.parse import urlsplit, quote, SplitResult, unquote

__all__ = [
    "Path",
    "LocalPath",
]

LOCAL_FILE_SCHEME = "os"
LOCAL_FILESYSTEM_START = "os://"
S3_FILESYSTEM_START = "s3://"

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


@dataclass(frozen=True)
class Path(abc.ABC):
    """
    URI-aware path (Hadoop-style): (scheme, authority, path).

    - POSIX normalization (forward slashes) for the path component
    - `__str__()`
    - `as_uri()` returns the full URI "scheme://authority/path"
    """

    scheme: str
    authority: str
    key: str
    query: Optional[str] = None
    fragment: Optional[str] = None

    @classmethod
    def parse_any(cls, obj: Any) -> Self:
        if isinstance(obj, Path):
            return obj

        if isinstance(obj, str):
            return cls.from_uri(obj)

        raise TypeError(f"Cannot parse {type(obj)} as Path")

    # ---- construction ----
    @classmethod
    def from_uri(cls, uri: str) -> Self:
        """Create from a full URI, e.g. s3://bucket/a/b.txt or file:///tmp/x."""
        if uri.startswith(LOCAL_FILESYSTEM_START):
            sp = urlsplit(uri)

            return LocalPath.from_url_split_result(sp)
        elif uri.startswith(S3_FILESYSTEM_START):
            from ..s3.path import S3Path

            sp = urlsplit(uri)
            return S3Path.from_url_split_result(sp)
        else:
            # Default to local filesystem
            absolute_path = os.path.abspath(uri)

            return LocalPath.from_uri_parts(
                scheme = LOCAL_FILE_SCHEME,
                netloc = "",
                path = absolute_path
            )

    @classmethod
    @abc.abstractmethod
    def default_scheme(cls):
        """Default scheme for local filesystem."""
        ...

    @classmethod
    @abc.abstractmethod
    def from_uri_parts(
        cls,
        scheme: str = LOCAL_FILE_SCHEME,
        netloc: str = "",
        path: str = "",
        query: Optional[str] = None,
        fragment: Optional[str] = None
    ) -> Self: ...

    @classmethod
    def from_url_split_result(cls, sp: SplitResult):
        return cls.from_uri_parts(
            scheme=sp.scheme,
            netloc=sp.netloc,
            path=unquote(sp.path),
            query=sp.query or None,
            fragment=sp.fragment or None
        )

    # ---- core properties (abstract) ----
    def with_scheme(self, value: str) -> Self:
        """Return a new instance with the same authority/path and a new scheme."""
        if value == self.scheme:
            return self

        return self.from_uri_parts(
            scheme=value,
            netloc=self.authority,
            path=self.path
        )

    def with_authority(self, value: str) -> Self:
        """Return a new instance with the same scheme/path and a new authority."""

        return self.from_uri_parts(
            scheme=self.scheme,
            netloc=unquote(value),
            path=self.path,
            query=self.query,
            fragment=self.fragment
        )

    @property
    def path(self) -> str:
        """Normalized POSIX path (absolute or relative)."""
        return "/" + self.key

    def with_path(self, value: str) -> Self:
        """Return a new instance with the same scheme/authority and a new path."""

        return self.from_uri_parts(
            scheme=self.scheme,
            netloc=self.authority,
            path=unquote(value),
            query=self.query,
            fragment=self.fragment
        )

    def with_key(self, key: str) -> Self:
        """Return a new instance with the same scheme/authority and a new key."""
        return self.with_path("/" + key.lstrip("/"))

    # ---- presentation ----
    def __str__(self) -> str:
        # Return the POSIX path only (tests rely on this).
        return self.as_uri()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_uri()})"

    def __truediv__(self: Self, other: str) -> Self:
        return self.joinpath(other)

    # ---- queries ----
    @property
    def parts(self) -> List[str]:
        if not self.key:
            return []

        parts = self.key.split("/")

        return parts[:-1] if parts[-1] == "" else parts

    @property
    def name(self) -> str:
        key = self.key

        if not key:
            return ""

        return posixpath.basename(key) if key[-1] != "/" else posixpath.basename(key[:-1])

    def with_name(self: Self, name: str) -> Self:
        return self.with_key(posixpath.join(self.parent.key, name))

    @property
    def parent(self: Self) -> Self:
        if self.is_root:
            raise ValueError("%s has no parent" % repr(self))

        key = _rstrip(self.key, "/")
        base = posixpath.dirname(key)

        return self.with_key(base)

    @property
    def suffix(self) -> str:
        b = self.name
        i = b.rfind(".")
        return b[i:] if i > 0 else ""

    @property
    def stem(self) -> str:
        b = self.name
        if not b:
            return ""
        i = b.rfind(".")
        return b[:i] if i > 0 else b

    @property
    def is_root(self) -> bool:
        return not bool(self.key)

    # ---- transforms ----
    def with_suffix(self: Self, suffix: str) -> Self:
        if suffix and not suffix.startswith("."):
            raise ValueError("suffix must start with '.'")
        if not self.name:
            raise ValueError("cannot set suffix on a directory path")
        return self.with_name(self.stem + suffix)

    def joinpath(self: Self, *segments: str) -> Self:
        p = self.parts

        for seg in segments:
            if not seg:
                continue
            if seg.startswith("/"):
                # absolute segment resets path
                p = [s for s in unquote(seg).strip("/").split("/") if s]
            else:
                p.extend(s for s in unquote(seg).split("/") if s)

        return self.with_key("/".join(p))

    def relative_to(self, other: "Path") -> Self:
        """
        Relative path (as a Path) from `other` to `self`.
        Requires same (scheme, authority).
        """
        if self.scheme != other.scheme or self.authority != other.authority:
            raise ValueError("Cannot compute relative path across different scheme/authority %s != %s" % (
                (self.scheme, self.authority), (other.scheme, other.authority)
            ))

        if (self.scheme, self.authority) != (other.scheme, other.authority):
            raise ValueError("Cannot compute relative path across different scheme/authority")

        rel = _relposix(other.path, self.path)

        return self.from_uri_parts(
            scheme=self.scheme,
            netloc=self.authority,
            path=rel,
            query=self.query,
            fragment=self.fragment
        )

    def as_uri(self) -> str:
        """Full URI with percent-encoding."""
        base = "%s://%s" % (
            self.scheme,
            quote("/".join((self.authority, self.key))),
        )

        if self.query:
            base += "?" + self.query

        if self.fragment:
            base += "#" + self.fragment

        return base


class LocalPath(Path):
    """
    Minimal concrete implementation of Path.

    Stores normalized POSIX path and carries scheme/authority.
    """

    @classmethod
    def default_scheme(cls):
        return LOCAL_FILE_SCHEME

    @classmethod
    def from_uri_parts(
        cls,
        scheme: str = LOCAL_FILE_SCHEME,
        netloc: str = "",
        path: str = "",
        query: Optional[str] = None,
        fragment: Optional[str] = None
    ) -> Self:
        if not path:
            path = "/"

        # Normalize to POSIX style
        if os.name == "nt":
            path = path.replace("\\", "/")

            # Find if starts with drive letter (e.g. C:/...) and set as authority
            if len(path) >= 2 and path[1] == ":" and path[2] == "/" and path[0].isalpha():
                netloc = path[0].upper() + ":"
                path = path[2:] or "/"

        path = posixpath.normpath(path)

        return cls(
            scheme=scheme or cls.default_scheme(),
            authority=netloc or "",
            key=path.lstrip("/"),
            query=query,
            fragment=fragment
        )


# ---- helpers ----

def _relposix(start: str, target: str) -> str:
    """Compute POSIX relative path string from start→target."""
    s = [s for s in start.strip("/").split("/") if s]
    t = [s for s in target.strip("/").split("/") if s]
    i = 0
    while i < len(s) and i < len(t) and s[i] == t[i]:
        i += 1
    up = [".."] * (len(s) - i)
    down = t[i:]
    rel = "/".join(up + down)
    return rel or "."

def _rstrip(s: str, suffix: str) -> str:
    """Like str.rstrip but for a fixed suffix."""
    if s.endswith(suffix):
        return s[:len(s)-len(suffix)]
    return s