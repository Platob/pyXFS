# pyxfs Path Utilities

[![PyPI version](https://badge.fury.io/py/pyxfs.svg)](https://pypi.org/project/pyxfs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`pyxfs` is a Python library that provides a **URI-aware path abstraction** similar to `pathlib`, but designed for distributed and cloud storage systems.

It supports **Hadoop-style** path components `(scheme, authority, path)` and provides concrete path classes for:
- **Local files** (`LocalPath`, scheme: `os://`)
- **S3 paths** (`S3Path`, scheme: `s3://` — in `pyxfs.s3.path`)

It normalizes paths to POSIX style (`/` separators), works with URIs, and provides high-level path manipulation utilities.

---

## Features

- Parse local and S3 URIs (`os:///tmp/file`, `s3://bucket/path/file`).
- Normalize paths (`/a/b/../c` → `/a/c`).
- Join, split, and modify paths without losing scheme/authority.
- Build paths from **absolute paths** or **URIs**.
- Generate safe URIs with percent-encoding for spaces and special characters.

---

## Installation

Install directly from PyPI:

```bash
pip install pyxfs
```

## Quickstart
```python
from pyxfs.path import Path, LocalPath

# Build from absolute local path
p = Path.from_uri("/tmp/data/file.txt")
print(p)              # os:///tmp/data/file.txt
print(p.scheme)       # os
print(p.parts)        # ['tmp', 'data', 'file.txt']
print(p.name)         # file.txt
print(p.suffix)       # .txt

# Build from os:// URI
p2 = Path.from_uri("os:///var/log/syslog")
print(p2.as_uri())    # os:///var/log/syslog

# Path operations
p3 = p2 / "archive" / "old.log"
print(p3)             # os:///var/log/archive/old.log

p4 = p3.with_name("latest.log")
print(p4)             # os:///var/log/archive/latest.log

p5 = p4.with_suffix(".gz")
print(p5)             # os:///var/log/archive/latest.gz

print(p5.parent)      # os:///var/log/archive
```

### S3 Path Example
```python
from pyxfs.path import Path

p = Path.from_uri("s3://my-bucket/data/file.csv")
print(p.scheme)     # s3
print(p.authority)  # my-bucket
print(p.parts)      # ['data', 'file.csv']
print(p.name)       # file.csv
print(p.as_uri())   # s3://my-bucket/data/file.csv
print(p.with_suffix(".json"))  # s3://my-bucket/data/file.json
```