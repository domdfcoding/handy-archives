# From https://github.com/python/cpython/blob/main/Lib/test/test_shutil.py
# Copyright (C) 2003 Python Software Foundation

# stdlib
import os
import pathlib
import unittest.mock
from shutil import (
		ReadError,
		RegistryError,
		get_archive_formats,
		get_unpack_formats,
		make_archive,
		register_archive_format,
		register_unpack_format,
		unregister_archive_format,
		unregister_unpack_format
		)
from typing import no_type_check

# 3rd party
import pytest
from domdf_python_tools.paths import TemporaryPathPlus

# this package
from handy_archives import unpack_archive
from tests.utils import TESTFN, requires_bz2, requires_lzma, requires_zlib

try:
	# stdlib
	from test.support import FakePath  # type: ignore[import]
except ImportError:
	# stdlib
	from test.support.os_helper import FakePath  # type: ignore[import]


def rlistdir(path):
	res = []
	for name in sorted(os.listdir(path)):
		p = os.path.join(path, name)
		if os.path.isdir(p) and not os.path.islink(p):
			res.append(name + '/')
			for n in rlistdir(p):
				res.append(name + '/' + n)
		else:
			res.append(name)
	return res


def write_file(path, content, binary=False):
	"""Write *content* to a file located at *path*.

	If *path* is a tuple instead of a string, os.path.join will be used to
	make a path.  If *binary* is true, the file will be opened in binary
	mode.
	"""
	if isinstance(path, tuple):
		path = os.path.join(*path)
	mode = "wb" if binary else 'w'
	encoding = None if binary else "utf-8"
	with open(path, mode, encoding=encoding) as fp:
		fp.write(content)


class TestArchives(unittest.TestCase):

	@no_type_check
	def test_register_archive_format(self):
		with pytest.raises(TypeError, match="The 1 object is not callable"):
			register_archive_format("xxx", 1)
		with pytest.raises(TypeError, match="extra_args needs to be a sequence"):
			register_archive_format("xxx", lambda: os, 1)
		with pytest.raises(TypeError, match=r"extra_args elements are : \(arg_name, value\)"):
			register_archive_format("xxx", lambda: os, [(1, 2), (1, 2, 3)])

		register_archive_format("xxx", lambda: os, [(1, 2)], "xxx file")
		formats = [name for name, params in get_archive_formats()]
		assert "xxx" in formats

		unregister_archive_format("xxx")
		formats = [name for name, params in get_archive_formats()]
		assert "xxx" not in formats

	### shutil.unpack_archive

	def check_unpack_archive(self, format):  # noqa: A002  # pylint: disable=redefined-builtin
		self.check_unpack_archive_with_converter(format, lambda path: path)
		self.check_unpack_archive_with_converter(format, pathlib.Path)
		self.check_unpack_archive_with_converter(format, FakePath)

	def check_unpack_archive_with_converter(
			self,
			format,  # noqa: A002  # pylint: disable=redefined-builtin
			converter,
			):
		base_dir = "dist"

		with TemporaryPathPlus() as root_dir:
			dist = os.path.join(root_dir, base_dir)
			os.makedirs(dist, exist_ok=True)
			write_file((dist, "file1"), "xxx")
			write_file((dist, "file2"), "xxx")
			os.mkdir(os.path.join(dist, "sub"))
			write_file((dist, "sub", "file3"), "xxx")
			os.mkdir(os.path.join(dist, "sub2"))
			write_file((root_dir, "outer"), "xxx")

			expected = rlistdir(root_dir)
			expected.remove("outer")

			with TemporaryPathPlus() as tmpdir:
				base_name = os.path.join(tmpdir, "archive")
				filename = make_archive(base_name, format, root_dir, base_dir)

				# let's try to unpack it now
				with TemporaryPathPlus() as tmpdir2:
					unpack_archive(converter(filename), converter(str(tmpdir2)))
					assert rlistdir(tmpdir2) == expected

				# and again, this time with the format specified
				with TemporaryPathPlus() as tmpdir3:
					unpack_archive(converter(filename), converter(str(tmpdir3)), format=format)
					assert rlistdir(tmpdir3) == expected

				with pytest.raises(ReadError, match="Unknown archive format "):
					unpack_archive(converter(TESTFN))
				with pytest.raises(ValueError, match="Unknown unpack format 'xxx'"):
					unpack_archive(converter(TESTFN), format="xxx")

	def test_unpack_archive_tar(self):
		self.check_unpack_archive("tar")

	@requires_zlib()
	def test_unpack_archive_gztar(self):
		self.check_unpack_archive("gztar")

	@requires_bz2()
	def test_unpack_archive_bztar(self):
		self.check_unpack_archive("bztar")

	@requires_lzma()
	def test_unpack_archive_xztar(self):
		self.check_unpack_archive("xztar")

	@requires_zlib()
	def test_unpack_archive_zip(self):
		self.check_unpack_archive("zip")

	def test_unpack_registry(self):

		formats = get_unpack_formats()

		def _boo(filename, extract_dir, extra):
			assert extra == 1
			assert filename == "stuff.boo"
			assert extract_dir == "xx"

		register_unpack_format("Boo", [".boo", ".b2"], _boo, [("extra", 1)])
		unpack_archive("stuff.boo", "xx")

		# trying to register a .boo unpacker again
		with pytest.raises(RegistryError):
			register_unpack_format("Boo2", [".boo"], _boo)  # type: ignore[arg-type]

		# should work now
		unregister_unpack_format("Boo")
		register_unpack_format("Boo2", [".boo"], _boo)  # type: ignore[arg-type]
		assert ("Boo2", [".boo"], '') in get_unpack_formats()
		assert ("Boo", [".boo"], '') not in get_unpack_formats()

		# let's leave a clean state
		unregister_unpack_format("Boo2")
		assert get_unpack_formats() == formats


# def teardown_module(module):
# 	for tmpdir in

if __name__ == "__main__":
	unittest.main()
