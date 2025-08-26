# src/pyxfs/fs.py
from __future__ import annotations

import abc
import io
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from .path import Path

StrPath = Union[str, Path]


@dataclass(frozen=True)
class DirEntry:
    """
    A directory listing entry.

    - path: full path of this entry (absolute within the backend)
    - name: base name of the entry
    - is_dir: True if this entry is a directory/prefix
    - size: size in bytes if known (files only)
    - mtime: modification time as UNIX epoch seconds if known
    - etag: remote/content hash if the backend exposes one (e.g. S3 ETag)
    """
    path: Path
    name: str
    is_dir: bool
    size: Optional[int] = None
    mtime: Optional[float] = None
    etag: Optional[str] = None


class FileSystem(abc.ABC):
    """
    Abstract filesystem interface for pyxfs.

    Implementations are rooted at a base location (e.g., local dir, S3 bucket/prefix).
    All methods accept either an `AbstractPath` or a POSIX string relative to the root.
    Concrete backends MUST implement the abstract methods below.
    """

    # ----- identity -----
    @property
    @abc.abstractmethod
    def root(self) -> Path:
        """Root path for this filesystem (scheme/authority/path)."""

    # ----- path helpers -----
    def _to_path(self, p: StrPath) -> Path:
        """Coerce a string to a backend-specific path relative to root; pass through AbstractPath."""
        if isinstance(p, Path):
            return p
        # Default join semantics: treat string as relative to root.path
        return self.root.joinpath(p)

    # ----- I/O primitives -----
    @abc.abstractmethod
    def open(self, path: StrPath, mode: str = "rb") -> io.IOBase:
        """Open a path for reading/writing. Binary/text mode must be honored."""

    @abc.abstractmethod
    def read_bytes(self, path: StrPath) -> bytes:
        """Read the entire file as bytes."""

    @abc.abstractmethod
    def write_bytes(self, path: StrPath, data: bytes) -> None:
        """Write the entire file from bytes, creating parent directories as needed."""

    # Convenience text wrappers
    def read_text(self, path: StrPath, encoding: str = "utf-8") -> str:
        return self.read_bytes(path).decode(encoding)

    def write_text(self, path: StrPath, text: str, encoding: str = "utf-8") -> None:
        self.write_bytes(path, text.encode(encoding))

    # ----- metadata / existence -----
    @abc.abstractmethod
    def exists(self, path: StrPath) -> bool:
        """True if a file or directory exists at path."""

    @abc.abstractmethod
    def is_dir(self, path: StrPath) -> bool:
        """True if path is a directory/prefix."""

    def is_file(self, path: StrPath) -> bool:
        return self.exists(path) and not self.is_dir(path)

    # ----- directory ops -----
    @abc.abstractmethod
    def ls(self, path: StrPath = ".", detail: bool = False) -> List[Union[str, DirEntry]]:
        """
        List a directory.

        - If detail=False (default): returns a list of child names (str).
        - If detail=True: returns a list of DirEntry with metadata when available.
        Should return an empty list for non-existent paths.
        """

    @abc.abstractmethod
    def mkdirs(self, path: StrPath, exist_ok: bool = True) -> None:
        """Create directories recursively."""

    @abc.abstractmethod
    def rm(self, path: StrPath, recursive: bool = False) -> None:
        """Remove a file. If recursive=True and path is a directory, remove its contents."""

    # ----- data movement -----
    @abc.abstractmethod
    def mv(self, src: StrPath, dst: StrPath, overwrite: bool = False) -> None:
        """Move/rename a file or directory."""

    @abc.abstractmethod
    def cp(self, src: StrPath, dst: StrPath, overwrite: bool = False) -> None:
        """Copy a file or directory (if supported)."""

    # ----- convenience utilities (default impls may be overridden) -----
    def glob(self, pattern: str) -> List[str]:
        """
        Simple glob under root using '*' and '?' within a *single* directory level.
        Backends are encouraged to override with more efficient implementations.
        """
        # naive fallback using ls of the parent directory
        import posixpath
        parent = posixpath.dirname(pattern) or "."
        mask = posixpath.basename(pattern)
        names = [n for n in self.ls(parent, detail=False)]
        import fnmatch
        return sorted([f"{parent}/{n}".lstrip("./") for n in names if fnmatch.fnmatch(n, mask)])

    def walk(self, top: StrPath = ".") -> Iterator[Tuple[str, List[str], List[str]]]:
        """
        Walk the directory tree rooted at `top`, yielding (dirpath, dirnames, filenames).
        Paths yielded are POSIX strings relative to the root.
        """
        import posixpath

        top_str = self._to_rel_str(top)
        entries = self.ls(top_str, detail=True)  # type: ignore[arg-type]
        dirs, files = [], []
        for e in entries:  # type: ignore[assignment]
            assert isinstance(e, DirEntry)
            if e.is_dir:
                dirs.append(e.name)
            else:
                files.append(e.name)
        yield top_str, sorted(dirs), sorted(files)
        for d in sorted(dirs):
            yield from self.walk(posixpath.join(top_str, d))

    # ----- helpers -----
    def _to_rel_str(self, p: StrPath) -> str:
        """
        Convert path to a POSIX string relative to root for display/walk/glob.
        """
        ap = self._to_path(p)
        # If same scheme/authority, compute relative; otherwise return absolute URI.
        if (ap.scheme, ap.authority) == (self.root.scheme, self.root.authority):
            try:
                return ap.relative_to(self.root)
            except Exception:
                pass
        return ap.path.lstrip("/")
