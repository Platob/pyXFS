from dataclasses import dataclass
from typing import Optional

from ..core.path import Path

__all__ = [
    "S3Path"
]


@dataclass(frozen=True)
class S3Path(Path):
    """S3Path represents an S3 object path with scheme, bucket (authority), and key (path)."""

    @classmethod
    def default_scheme(cls):
        return "s3"

    @classmethod
    def from_uri_parts(
        cls,
        scheme: str = "s3",
        netloc: str = "",
        path: str = "",
        query: Optional[str] = None,
        fragment: Optional[str] = None
    ):
        bucket = netloc
        key = path.lstrip("/") if path else ""

        return cls(
            scheme=scheme or cls.default_scheme(),
            authority=bucket,
            key=key,
            query=query,
            fragment=fragment
        )

    @property
    def bucket(self) -> str:
        """The S3 bucket name (authority)."""
        return self.authority
