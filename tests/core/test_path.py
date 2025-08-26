import unittest

from pyxfs.core.path import Path, LocalPath
from pyxfs.s3.path import S3Path


class TestPath(unittest.TestCase):

    def test_from_uri_s3_basic(self):
        p = Path.from_uri("s3://my-bucket/a/b/c.txt")
        self.assertIsInstance(p, Path)
        self.assertIsInstance(p, S3Path)
        self.assertEqual(p.scheme, "s3")
        self.assertEqual(p.authority, "my-bucket")
        self.assertEqual(p.parts, ["a", "b", "c.txt"])
        self.assertEqual(p.name, "c.txt")
        self.assertEqual(p.stem, "c")
        self.assertEqual(p.suffix, ".txt")
        self.assertEqual(str(p), "s3://my-bucket/a/b/c.txt")
        self.assertEqual(p.as_uri(), "s3://my-bucket/a/b/c.txt")

    def test_parent_and_join_preserve_scheme_authority(self):
        p = Path.from_uri("s3://bkt/x/y")
        q = p.parent / "z.dat"
        self.assertEqual(q.scheme, "s3")
        self.assertEqual(q.authority, "bkt")
        self.assertEqual(str(q), "s3://bkt/x/z.dat")
        self.assertEqual(q.as_uri(), "s3://bkt/x/z.dat")

    def test_parent_with_slash(self):
        p = Path.from_uri("s3://bkt/x/y/")
        self.assertEqual(p.parts, ["x", "y"])
        self.assertEqual(p.name, "y")
        self.assertEqual(p.parent.as_uri(), "s3://bkt/x")

    def test_with_suffix_and_with_name(self):
        p = Path.from_uri("s3://bkt/a/b/c.tar.gz")
        p2 = p.with_suffix(".zip")
        self.assertEqual(p2.name, "c.tar.zip")
        self.assertEqual(p2.as_uri(), "s3://bkt/a/b/c.tar.zip")

        p3 = p2.with_name("final.parquet")
        self.assertEqual(p3.name, "final.parquet")
        self.assertEqual(p3.as_uri(), "s3://bkt/a/b/final.parquet")

    def test_relative_to_same_root(self):
        base = Path.from_uri("s3://bkt/a")
        target = Path.from_uri("s3://bkt/a/b/c.txt")
        rel = target.relative_to(base)
        self.assertIsInstance(rel, Path)
        self.assertIsInstance(rel, S3Path)
        self.assertEqual(rel.scheme, "s3")
        self.assertEqual(rel.authority, "bkt")
        self.assertEqual(str(rel), "s3://bkt/b/c.txt")

    def test_relative_to_different_roots_raises(self):
        p1 = Path.from_uri("s3://bucket1/a/b")
        p2 = Path.from_uri("s3://bucket2/a/b")
        with self.assertRaises(ValueError):
            _ = p1.relative_to(p2)

    def test_file_scheme_and_roundtrip(self):
        p = Path.from_uri("os:///tmp/data/hello.txt")
        self.assertEqual(p.scheme, "os")
        # file: empty authority (netloc)
        self.assertEqual(p.parts, ["tmp", "data", "hello.txt"])
        self.assertEqual(p.authority, "")
        self.assertEqual(p.parts[-1], "hello.txt")
        self.assertEqual(p.as_uri(), "os:///tmp/data/hello.txt")

    def test_root_and_dir_behavior(self):
        root = Path.from_uri("s3://bkt/")
        self.assertEqual(root.parts, [])
        self.assertEqual(root.as_uri(), "s3://bkt/")
        self.assertTrue(root.is_root)

        child = root / "dir" / "sub" / "file.bin"
        self.assertEqual(child.parts, ["dir", "sub", "file.bin"])
        self.assertEqual(child.parent.as_uri(), "s3://bkt/dir/sub")

    def test_joinpath_absolute_segment_resets_path(self):
        p = Path.from_uri("s3://bkt/a/b")
        q = p.joinpath("/c/d")  # absolute POSIX segment; should replace path
        self.assertEqual(q.parts, ["c", "d"])
        self.assertEqual(q.as_uri(), "s3://bkt/c/d")
        self.assertEqual((q.scheme, q.authority), ("s3", "bkt"))

    def test_preserve_scheme_authority_on_ops(self):
        p = Path.from_uri("s3://bkt/a/b/c.txt")
        for op in [
            lambda x: x.parent,
            lambda x: x.with_name("x.parquet"),
            lambda x: x.with_suffix(".log"),
            lambda x: x.joinpath("more"),
        ]:
            q = op(p)
            self.assertIsInstance(q, Path)
            self.assertEqual((q.scheme, q.authority), ("s3", "bkt"))

    def test_url_encoding_and_decoding(self):
        # spaces + unicode
        p = Path.from_uri("s3://bkt/a dir/☃.txt")
        uri = p.as_uri()
        self.assertEqual(uri, "s3://bkt/a%20dir/%E2%98%83.txt")
        back = Path.from_uri(uri)
        self.assertEqual(back, p)

    def test_from_absolute_posix_path(self):
        import os as os_module
        orig_name = os_module.name
        os_module.name = "nt"

        try:
            abs_path = "/tmp/folder/file.txt"
            p = Path.from_uri(abs_path)
            print(p)
            self.assertIsInstance(p, LocalPath)
            self.assertEqual(p.scheme, "os")
            self.assertEqual(p.authority, "C:")
            self.assertEqual(p.path, abs_path)
        finally:
            os_module.name = orig_name

    def test_from_uri_os_scheme(self):
        uri = "os:///var/data/file.bin"
        p = Path.from_uri(uri)
        self.assertIsInstance(p, LocalPath)
        self.assertEqual(p.scheme, "os")
        self.assertEqual(p.as_uri(), uri)
        self.assertEqual(p.parts, ["var", "data", "file.bin"])

    def test_normalization_of_posix_path(self):
        p = LocalPath.from_uri_parts(
            scheme="os",
            netloc="",
            path="/a/b/../c//./d"
        )
        self.assertEqual(p.path, "/a/c/d")

    def test_windows_path_backslash_conversion(self):
        import os as os_module
        orig_name = os_module.name
        os_module.name = "nt"
        try:
            p = LocalPath.from_uri_parts(
                scheme="os",
                netloc="",
                path="C:\\folder\\sub\\file.txt"
            )
            self.assertEqual(p.authority, "C:")
            self.assertIn("/", p.path)
            self.assertNotIn("\\", p.path)
        finally:
            os_module.name = orig_name


if __name__ == "__main__":
    unittest.main()
