
from pyxfs import LocalFS

def test_local_roundtrip(tmp_path):
    fs = LocalFS(tmp_path)
    fs.makedirs("x/y", exist_ok=True)
    fs.write_text("x/y/hello.txt", "hi")
    assert fs.read_text("x/y/hello.txt") == "hi"
    assert "hello.txt" in "\n".join(fs.ls("x/y"))
    fs.cp("x/y/hello.txt", "x/y/hello_copy.txt")
    assert fs.exists("x/y/hello_copy.txt")
    fs.mv("x/y/hello_copy.txt", "x/y/hello_moved.txt", overwrite=True)
    assert fs.exists("x/y/hello_moved.txt")
    fs.rm("x", recursive=True)
    assert not fs.exists("x")
