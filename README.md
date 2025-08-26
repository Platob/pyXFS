
# pyxfs — a universal filesystem interface

`pyxfs` provides a simple, Pythonic abstraction over multiple storage backends
(local disk, S3, SFTP, and more). Start with the same API everywhere; plug in
additional backends via extras.

## Installation

```bash
pip install pyxfs          # core (local only)
pip install "pyxfs[s3]"    # add S3 support (boto3)
pip install "pyxfs[sftp]"  # add SFTP support (paramiko)
```

## Quick start

```python
from pyxfs import open_fs

fs = open_fs("file:///tmp")        # local
# fs = open_fs("s3://my-bucket")   # S3 (requires boto3)
# fs = open_fs("sftp://user@host") # SFTP (requires paramiko)

fs.makedirs("data", exist_ok=True)
fs.write_text("data/hello.txt", "hi")
print(fs.read_text("data/hello.txt"))
print(fs.ls("data"))
```

## Philosophy
- Minimal core, small surface area
- Batteries-included local backend
- Optional, cleanly isolated cloud/remote backends
- Type hints and friendly errors

## License
MIT
