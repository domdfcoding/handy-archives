# From https://github.com/python/cpython/blob/main/Lib/test/test_tarfile.py
# Copyright (C) 2003 Python Software Foundation
# type: ignore

# stdlib
import io
import os
import pathlib
import re
import sys
import tarfile
import unittest.mock
from collections.abc import Callable
from contextlib import suppress
from hashlib import sha256
from random import Random
from test.support import findfile, gc_collect, swap_attr
from typing import Optional, Type

# 3rd party
import pytest
from coincidence import min_version
from domdf_python_tools.paths import PathPlus, TemporaryPathPlus, in_directory

# this package
from handy_archives import TarFile, is_tarfile
from tests.utils import requires_bz2, requires_gzip, requires_lzma, skip_unless_symlink

try:
	# stdlib
	from test.support import create_empty_file, rmdir, rmtree, temp_dir, unlink
except ImportError:
	# stdlib
	from test.support.os_helper import create_empty_file, rmdir, rmtree, temp_dir, unlink

# Check for our compression modules.
try:
	# stdlib
	import gzip
except ImportError:
	gzip = None
try:
	# stdlib
	import bz2
except ImportError:
	bz2 = None
try:
	# stdlib
	import lzma
except ImportError:
	lzma = None


def sha256sum(data):
	return sha256(data).hexdigest()


tarname = findfile("testtar.tar")
sha256_regtype = ("e09e4bc8b3c9d9177e77256353b36c159f5f040531bbd4b024a8f9b9196c71ce")
sha256_sparse = ("4f05a776071146756345ceee937b33fc5644f5a96b9780d1c7d6a32cdf164d7b")


class TarTest:
	tarname = tarname
	suffix = ''
	open = io.FileIO  # noqa: A003  # pylint: disable=redefined-builtin
	taropen = TarFile.taropen
	prefix: str

	@property
	def mode(self):
		return self.prefix + self.suffix


class BaseTest:
	tarname: str
	suffix: str
	open: Optional[Type]  # noqa: A003  # pylint: disable=redefined-builtin
	taropen: Callable


@requires_gzip()
class GzipTest(BaseTest):
	suffix = "gz"
	open = gzip.GzipFile if gzip else None  # noqa: A003  # pylint: disable=redefined-builtin
	taropen = TarFile.gzopen

	@pytest.fixture(autouse=True)
	def _tarfile(self, tmp_pathplus: PathPlus):
		os.path.join(tmp_pathplus, "testtar.tar.gz")
		self.tarname = "testtar.tar.gz"

		with open(tarname, "rb") as fobj:
			data = fobj.read()

		if self.open:
			unlink(tmp_pathplus / self.tarname)
			with self.open(tmp_pathplus / self.tarname, "wb") as tar:
				tar.write(data)

		self.tar = TarFile.open(tmp_pathplus / self.tarname, mode=self.mode, encoding="iso8859-1")


@requires_bz2()
class Bz2Test(BaseTest):
	suffix = "bz2"
	open = bz2.BZ2File if bz2 else None  # noqa: A003  # pylint: disable=redefined-builtin
	taropen = TarFile.bz2open

	@pytest.fixture(autouse=True)
	def _tarfile(self, tmp_pathplus: PathPlus):
		os.path.join(tmp_pathplus, "testtar.tar.bz2")
		self.tarname = "testtar.tar.bz2"

		with open(tarname, "rb") as fobj:
			data = fobj.read()

		if self.open:
			unlink(tmp_pathplus / self.tarname)
			with self.open(tmp_pathplus / self.tarname, "wb") as tar:
				tar.write(data)

		self.tar = TarFile.open(tmp_pathplus / self.tarname, mode=self.mode, encoding="iso8859-1")


@requires_lzma()
class LzmaTest(BaseTest):
	suffix = "xz"
	open = lzma.LZMAFile if lzma else None  # noqa: A003  # pylint: disable=redefined-builtin
	taropen = TarFile.xzopen

	@pytest.fixture(autouse=True)
	def _tarfile(self, tmp_pathplus: PathPlus):
		os.path.join(tmp_pathplus, "testtar.tar.xz")
		self.tarname = "testtar.tar.xz"

		with open(tarname, "rb") as fobj:
			data = fobj.read()

		if self.open:
			unlink(tmp_pathplus / self.tarname)
			with self.open(tmp_pathplus / self.tarname, "wb") as tar:
				tar.write(data)

		self.tar = TarFile.open(tmp_pathplus / self.tarname, mode=self.mode, encoding="iso8859-1")


class ReadTest(TarTest):

	prefix = "r:"

	@pytest.fixture(autouse=True)
	def _tarfile(self, tmp_pathplus: PathPlus):
		self.tar = TarFile.open(tmp_pathplus / self.tarname, mode=self.mode, encoding="iso8859-1")


class TestUstarRead(ReadTest):

	def test_fileobj_regular_file(self):
		tarinfo = self.tar.getmember("ustar/regtype")
		with self.tar.extractfile(tarinfo) as fobj:
			data = fobj.read()
			assert len(data) == tarinfo.size, "regular file extraction failed"
			assert sha256sum(data) == sha256_regtype, "regular file extraction failed"

	def test_fileobj_readlines(self, tmp_pathplus: PathPlus):
		self.tar.extract("ustar/regtype", tmp_pathplus)
		tarinfo = self.tar.getmember("ustar/regtype")
		with open(os.path.join(tmp_pathplus, "ustar/regtype"), encoding="UTF-8") as fobj1:
			lines1 = fobj1.readlines()

		with self.tar.extractfile(tarinfo) as fobj:
			fobj2 = io.TextIOWrapper(fobj)
			lines2 = fobj2.readlines()
			assert lines1 == lines2, "fileobj.readlines() failed"
			assert len(lines2) == 114, "fileobj.readlines() failed"
			assert lines2[83] == "I will gladly admit that Python is not the fastest " "running scripting language.\n", "fileobj.readlines() failed"

	def test_fileobj_iter(self, tmp_pathplus: PathPlus):
		self.tar.extract("ustar/regtype", tmp_pathplus)
		tarinfo = self.tar.getmember("ustar/regtype")
		with open(os.path.join(tmp_pathplus, "ustar/regtype"), encoding="UTF-8") as fobj1:
			lines1 = fobj1.readlines()
		with self.tar.extractfile(tarinfo) as fobj2:
			lines2 = list(io.TextIOWrapper(fobj2))
			assert lines1 == lines2, "fileobj.__iter__() failed"

	def test_fileobj_seek(self, tmp_pathplus: PathPlus):
		self.tar.extract("ustar/regtype", tmp_pathplus)
		with open(os.path.join(tmp_pathplus, "ustar/regtype"), "rb") as fobj:
			data = fobj.read()

		tarinfo = self.tar.getmember("ustar/regtype")
		with self.tar.extractfile(tarinfo) as fobj:
			fobj.read()
			fobj.seek(0)
			assert 0 == fobj.tell(), "seek() to file's start failed"
			fobj.seek(2048, 0)
			assert 2048 == fobj.tell(), "seek() to absolute position failed"
			fobj.seek(-1024, 1)
			assert 1024 == fobj.tell(), "seek() to negative relative position failed"
			fobj.seek(1024, 1)
			assert 2048 == fobj.tell(), "seek() to positive relative position failed"
			s = fobj.read(10)
			assert s == data[2048:2058], "read() after seek failed"
			fobj.seek(0, 2)
			assert tarinfo.size == fobj.tell(), "seek() to file's end failed"
			assert fobj.read() == b"", "read() at file's end did not return empty string"
			fobj.seek(-tarinfo.size, 2)
			assert 0 == fobj.tell(), "relative seek() to file's end failed"
			fobj.seek(512)
			s1 = fobj.readlines()
			fobj.seek(512)
			s2 = fobj.readlines()
			assert s1 == s2, "readlines() after seek failed"
			fobj.seek(0)
			assert len(fobj.readline()) == fobj.tell(), "tell() after readline() failed"
			fobj.seek(512)
			assert len(fobj.readline()) + 512 == fobj.tell(), "tell() after seek() and readline() failed"
			fobj.seek(0)
			line = fobj.readline()
			assert fobj.read() == data[len(line):], "read() after readline() failed"

	def test_fileobj_text(self):
		with self.tar.extractfile("ustar/regtype") as fobj:
			fobj = io.TextIOWrapper(fobj)
			data = fobj.read().encode("iso8859-1")
			assert sha256sum(data) == sha256_regtype
			try:
				fobj.seek(100)
			except AttributeError:
				# Issue #13815: seek() complained about a missing
				# flush() method.
				pytest.fail("seeking failed in text mode")

	# Test if symbolic and hard links are resolved by extractfile().  The
	# test link members each point to a regular member whose data is
	# supposed to be exported.
	def _test_fileobj_link(self, lnktype, regtype):
		with self.tar.extractfile(lnktype) as a, self.tar.extractfile(regtype) as b:
			assert a.name == b.name

	def test_fileobj_link1(self):
		self._test_fileobj_link("ustar/lnktype", "ustar/regtype")

	def test_fileobj_link2(self):
		self._test_fileobj_link("./ustar/linktest2/lnktype", "ustar/linktest1/regtype")

	def test_fileobj_symlink1(self):
		self._test_fileobj_link("ustar/symtype", "ustar/regtype")

	def test_fileobj_symlink2(self):
		self._test_fileobj_link("./ustar/linktest2/symtype", "ustar/linktest1/regtype")

	def test_issue14160(self):
		self._test_fileobj_link("symtype2", "ustar/regtype")


class TestGzipUstarRead(GzipTest, TestUstarRead):
	pass


class TestBz2UstarRead(Bz2Test, TestUstarRead):
	pass


class TestLzmaUstarRead(LzmaTest, TestUstarRead):
	pass


class TestList(ReadTest):

	@pytest.fixture(autouse=True)
	def _tarfile(self, tmp_pathplus: PathPlus):
		self.tar = TarFile.open(tmp_pathplus / self.tarname, mode=self.mode)

	def test_list(self):
		tio = io.TextIOWrapper(io.BytesIO(), "ascii", newline='\n')
		with swap_attr(sys, "stdout", tio):
			self.tar.list(verbose=False)
		out = tio.detach().getvalue()
		assert b'ustar/conttype' in out
		assert b'ustar/regtype' in out
		assert b'ustar/lnktype' in out
		assert b'ustar' + (b'/12345' * 40) + b'67/longname' in out
		assert b'./ustar/linktest2/symtype' in out
		assert b'./ustar/linktest2/lnktype' in out
		# Make sure it puts trailing slash for directory
		assert b'ustar/dirtype/' in out
		assert b'ustar/dirtype-with-size/' in out

		# Make sure it is able to print unencodable characters
		def conv(b):
			s = b.decode(self.tar.encoding, "surrogateescape")
			return s.encode("ascii", "backslashreplace")

		assert conv(b'ustar/umlauts-\xc4\xd6\xdc\xe4\xf6\xfc\xdf') in out
		assert conv(b'misc/regtype-hpux-signed-chksum-\xc4\xd6\xdc\xe4\xf6\xfc\xdf') in out
		assert conv(b'misc/regtype-old-v7-signed-chksum-\xc4\xd6\xdc\xe4\xf6\xfc\xdf') in out
		assert conv(b'pax/bad-pax-\xe4\xf6\xfc') in out
		assert conv(b'pax/hdrcharset-\xe4\xf6\xfc') in out
		# Make sure it prints files separated by one newline without any
		# 'ls -l'-like accessories if verbose flag is not being used
		# ...
		# ustar/conttype
		# ustar/regtype
		# ...
		assert re.search(br'ustar/conttype ?\r?\nustar/regtype ?\r?\n', out)
		# Make sure it does not print the source of link without verbose flag
		assert b'link to' not in out
		assert b'->' not in out

	def test_list_verbose(self):
		tio = io.TextIOWrapper(io.BytesIO(), "ascii", newline='\n')
		with swap_attr(sys, "stdout", tio):
			self.tar.list(verbose=True)
		out = tio.detach().getvalue()
		# Make sure it prints files separated by one newline with 'ls -l'-like
		# accessories if verbose flag is being used
		# ...
		# ?rw-r--r-- tarfile/tarfile     7011 2003-01-06 07:19:43 ustar/conttype
		# ?rw-r--r-- tarfile/tarfile     7011 2003-01-06 07:19:43 ustar/regtype
		# ...
		assert re.search((
				br'\?rw-r--r-- tarfile/tarfile\s+7011 '
				br'\d{4}-\d\d-\d\d\s+\d\d:\d\d:\d\d '
				br'ustar/\w+type ?\r?\n'
				) * 2,
							out)
		# Make sure it prints the source of link with verbose flag
		assert b'ustar/symtype -> regtype' in out
		assert b'./ustar/linktest2/symtype -> ../linktest1/regtype' in out
		assert b'./ustar/linktest2/lnktype link to ' b'./ustar/linktest1/regtype' in out
		assert b'gnu' + (b'/123' * 125) + b'/longlink link to gnu' + (b'/123' * 125) + b'/longname' in out
		assert b'pax' + (b'/123' * 125) + b'/longlink link to pax' + (b'/123' * 125) + b'/longname' in out

	def test_list_members(self):
		tio = io.TextIOWrapper(io.BytesIO(), "ascii", newline='\n')

		def members(tar):
			for tarinfo in tar.getmembers():
				if "reg" in tarinfo.name:
					yield tarinfo

		with swap_attr(sys, "stdout", tio):
			self.tar.list(verbose=False, members=members(self.tar))
		out = tio.detach().getvalue()
		assert b'ustar/regtype' in out
		assert b'ustar/conttype' not in out


class TestGzipList(GzipTest, TestList):
	pass


class TestBz2List(Bz2Test, TestList):
	pass


class TestLzmaList(LzmaTest, TestList):
	pass


class CommonReadTest(ReadTest):

	def test_is_tarfile_erroneous(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with open(tmpname, "wb"):
				pass

			# is_tarfile works on filenames
			assert not is_tarfile(tmpname)

			# is_tarfile works on path-like objects
			assert not is_tarfile(pathlib.Path(tmpname))

			# is_tarfile works on file objects
			with open(tmpname, "rb") as fobj:
				assert not is_tarfile(fobj)

			# is_tarfile works on file-like objects
			assert not is_tarfile(io.BytesIO(b"invalid"))

	def test_is_tarfile_valid(self, tmp_pathplus: PathPlus):
		# is_tarfile works on filenames
		assert is_tarfile(str(tmp_pathplus / self.tarname))

		# is_tarfile works on path-like objects
		assert is_tarfile(tmp_pathplus / self.tarname)

		# is_tarfile works on file objects
		with open(tmp_pathplus / self.tarname, "rb") as fobj:
			assert is_tarfile(fobj)

		# is_tarfile works on file-like objects
		with open(tmp_pathplus / self.tarname, "rb") as fobj:
			assert is_tarfile(io.BytesIO(fobj.read()))

	def test_empty_tarfile(self):
		# Test for issue6123: Allow opening empty archives.
		# This test checks if TarFile.open() is able to open an empty tar
		# archive successfully. Note that an empty tar archive is not the
		# same as an empty file!

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode.replace('r', 'w')):
				pass
			try:
				tar = TarFile.open(tmpname, self.mode)
				tar.getnames()
			except tarfile.ReadError:
				pytest.fail("tarfile.open() failed on empty archive")
			else:
				assert tar.getmembers() == []
			finally:
				tar.close()

	def test_non_existent_tarfile(self):
		# Test for issue11513: prevent non-existent gzipped tarfiles raising
		# multiple exceptions.
		with pytest.raises(FileNotFoundError, match="xxx"):
			TarFile.open("xxx", self.mode)

	def test_null_tarfile(self):
		# Test for issue6123: Allow opening empty archives.
		# This test guarantees that TarFile.open() does not treat an empty
		# file as an empty tar archive.
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with open(tmpname, "wb"):
				pass
			with pytest.raises(tarfile.ReadError):
				TarFile.open(tmpname, self.mode)
			with pytest.raises(tarfile.ReadError):
				TarFile.open(tmpname)

	@min_version(3.9)
	def test_ignore_zeros(self):
		# Test TarFile's ignore_zeros option.
		# generate 512 pseudorandom bytes

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			data = Random(0).randbytes(512)
			for char in (b'\0', b'a'):
				# Test if EOFHeaderError ('\0') and InvalidHeaderError ('a')
				# are ignored correctly.
				with self.open(tmpname, 'w') as fobj:
					fobj.write(char * 1024)
					tarinfo = tarfile.TarInfo("foo")
					tarinfo.size = len(data)
					fobj.write(tarinfo.tobuf())
					fobj.write(data)

				tar = TarFile.open(tmpname, mode='r', ignore_zeros=True)
				try:
					assert tar.getnames() == ["foo"], f"ignore_zeros=True should have skipped the {char!r}-blocks"
				finally:
					tar.close()

	def test_premature_end_of_archive(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			for size in (512, 600, 1024, 1200):
				with TarFile.open(tmpname, "w:") as tar:
					t = tarfile.TarInfo("foo")
					t.size = 1024
					tar.addfile(t, io.BytesIO(b"a" * 1024))

				with open(tmpname, "r+b") as fobj:
					fobj.truncate(size)

				with TarFile.open(tmpname) as tar:
					with pytest.raises(tarfile.ReadError, match="unexpected end of data"):
						list(tar)

				with TarFile.open(tmpname) as tar:
					t = tar.next()

					with pytest.raises(tarfile.ReadError, match="unexpected end of data"):
						tar.extract(t, tmp_pathplus)

					with pytest.raises(tarfile.ReadError, match="unexpected end of data"):
						tar.extractfile(t).read()

	@pytest.mark.xfail(condition=sys.platform == "win32", reason="May not have been patched")
	def test_length_zero_header(self):
		# bpo-39017 (CVE-2019-20907): reading a zero-length header should fail with an exception
		with pytest.raises(tarfile.ReadError, match="file could not be opened successfully"):
			with TarFile.open(findfile("recursion.tar")):
				pass


class MiscReadTestBase(CommonReadTest):

	def requires_name_attribute(self):
		pass

	def test_no_name_argument(self, tmp_pathplus: PathPlus):
		self.requires_name_attribute()
		with open(tmp_pathplus / self.tarname, "rb") as fobj:
			assert isinstance(fobj.name, str)
			with TarFile.open(fileobj=fobj, mode=self.mode) as tar:
				assert isinstance(tar.name, str)
				assert tar.name == os.path.abspath(fobj.name)

	def test_no_name_attribute(self, tmp_pathplus: PathPlus):
		with open(tmp_pathplus / self.tarname, "rb") as fobj:
			data = fobj.read()
		fobj = io.BytesIO(data)
		with pytest.raises(AttributeError):
			getattr(fobj, "name")
		tar = TarFile.open(fileobj=fobj, mode=self.mode)
		assert tar.name is None

	def test_empty_name_attribute(self, tmp_pathplus: PathPlus):
		with open(tmp_pathplus / self.tarname, "rb") as fobj:
			data = fobj.read()
		fobj = io.BytesIO(data)
		fobj.name = ''
		with TarFile.open(fileobj=fobj, mode=self.mode) as tar:
			assert tar.name is None

	def test_int_name_attribute(self, tmp_pathplus: PathPlus):
		# Issue 21044: TarFile.open() should handle fileobj with an integer
		# 'name' attribute.
		fd = os.open(tmp_pathplus / self.tarname, os.O_RDONLY)
		with open(fd, "rb") as fobj:
			assert isinstance(fobj.name, int)
			with TarFile.open(fileobj=fobj, mode=self.mode) as tar:
				assert tar.name is None

	def test_bytes_name_attribute(self, tmp_pathplus: PathPlus):
		self.requires_name_attribute()
		tarname = os.fsencode(tmp_pathplus / self.tarname)
		with open(tarname, "rb") as fobj:
			assert isinstance(fobj.name, bytes)
			with TarFile.open(fileobj=fobj, mode=self.mode) as tar:
				assert isinstance(tar.name, bytes)
				assert tar.name == os.path.abspath(fobj.name)

	def test_pathlike_name(self, tmp_pathplus: PathPlus):
		tarname = pathlib.Path(tmp_pathplus / self.tarname)
		with TarFile.open(tarname, mode=self.mode) as tar:
			assert isinstance(tar.name, str)
			assert tar.name == os.path.abspath(os.fspath(tarname))
		with self.taropen(tarname) as tar:
			assert isinstance(tar.name, str)
			assert tar.name == os.path.abspath(os.fspath(tarname))
		with TarFile.open(tarname, mode=self.mode) as tar:
			assert isinstance(tar.name, str)
			assert tar.name == os.path.abspath(os.fspath(tarname))
		if self.suffix == '':
			with TarFile(tarname, mode='r') as tar:
				assert isinstance(tar.name, str)
				assert tar.name == os.path.abspath(os.fspath(tarname))

	def test_illegal_mode_arg(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with open(tmpname, "wb"):
				pass
			with pytest.raises(ValueError, match="mode must be "):
				tar = self.taropen(tmpname, 'q')
			with pytest.raises(ValueError, match="mode must be "):
				tar = self.taropen(tmpname, "rw")
			with pytest.raises(ValueError, match="mode must be "):
				tar = self.taropen(tmpname, '')

	def test_fileobj_with_offset(self, tmp_pathplus: PathPlus):
		# Skip the first member and store values from the second member
		# of the testtar.
		tar = TarFile.open(tmp_pathplus / self.tarname, mode=self.mode)
		try:
			tar.next()
			t = tar.next()
			name = t.name
			offset = t.offset
			with tar.extractfile(t) as f:
				data = f.read()
		finally:
			tar.close()

		# Open the testtar and seek to the offset of the second member.
		with self.open(tmp_pathplus / self.tarname) as fobj:
			fobj.seek(offset)

			# Test if the tarfile starts with the second member.
			with tar.open(tmp_pathplus / self.tarname, mode="r:", fileobj=fobj) as tar:
				t = tar.next()
				assert t.name == name
				# Read to the end of fileobj and test if seeking back to the
				# beginning works.
				tar.getmembers()
				assert tar.extractfile(t).read() == data, "seek back did not work"

	def test_fail_comp(self):
		# For Gzip and Bz2 Tests: fail with a ReadError on an uncompressed file.
		with pytest.raises(tarfile.ReadError):
			TarFile.open(tarname, self.mode)
		with open(tarname, "rb") as fobj:
			with pytest.raises(tarfile.ReadError):
				TarFile.open(fileobj=fobj, mode=self.mode)

	def test_v7_dirtype(self):
		# Test old style dirtype member (bug #1336623):
		# Old V7 tars create directory members using an AREGTYPE
		# header with a "/" appended to the filename field.
		tarinfo = self.tar.getmember("misc/dirtype-old-v7")
		assert tarinfo.type == tarfile.DIRTYPE, "v7 dirtype failed"

	def test_xstar_type(self):
		# The xstar format stores extra atime and ctime fields inside the
		# space reserved for the prefix field. The prefix field must be
		# ignored in this case, otherwise it will mess up the name.
		try:
			self.tar.getmember("misc/regtype-xstar")
		except KeyError:
			pytest.fail("failed to find misc/regtype-xstar (mangled prefix?)")

	def test_check_members(self):
		for tarinfo in self.tar:
			assert int(tarinfo.mtime) == 0o7606136617, f"wrong mtime for {tarinfo.name}"
			if not tarinfo.name.startswith("ustar/"):
				continue
			assert tarinfo.uname == "tarfile", f"wrong uname for {tarinfo.name}"

	def test_find_members(self):
		assert self.tar.getmembers()[-1].name == "misc/eof", "could not find all members"

	@pytest.mark.skipif(not hasattr(os, "link"), reason="Missing hardlink implementation")
	@skip_unless_symlink
	def test_extract_hardlink(self, tmp_pathplus: PathPlus):
		# Test hardlink extraction (e.g. bug #857297).
		with TarFile.open(tarname, errorlevel=1, encoding="iso8859-1") as tar:
			tar.extract("ustar/regtype", tmp_pathplus)

			tar.extract("ustar/lnktype", tmp_pathplus)

			with open(os.path.join(tmp_pathplus, "ustar/lnktype"), "rb") as f:
				data = f.read()

			assert sha256sum(data) == sha256_regtype

			tar.extract("ustar/symtype", tmp_pathplus)

			with open(os.path.join(tmp_pathplus, "ustar/symtype"), "rb") as f:
				data = f.read()

			assert sha256sum(data) == sha256_regtype

	def test_extractall(self, tmp_pathplus: PathPlus):
		# Test if extractall() correctly restores directory permissions
		# and times (see issue1735).
		tar = TarFile.open(tarname, encoding="iso8859-1")
		DIR = os.path.join(tmp_pathplus, "extractall")
		os.mkdir(DIR)
		try:
			directories = [t for t in tar if t.isdir()]
			tar.extractall(DIR, directories)
			for tarinfo in directories:
				path = os.path.join(DIR, tarinfo.name)
				if sys.platform != "win32":
					# Win32 has no support for fine grained permissions.
					assert tarinfo.mode & 0o777 == os.stat(path).st_mode & 0o777

				def format_mtime(mtime):
					if isinstance(mtime, float):
						return f"{mtime} ({mtime.hex()})"
					else:
						return f"{mtime!r} (int)"

				file_mtime = os.path.getmtime(path)
				errmsg = "tar mtime {} != file time {} of path {!a}".format(
						format_mtime(tarinfo.mtime), format_mtime(file_mtime), path
						)
				assert tarinfo.mtime == file_mtime, errmsg
		finally:
			tar.close()

	def test_extract_directory(self, tmp_pathplus: PathPlus):
		dirtype = "ustar/dirtype"
		DIR = os.path.join(tmp_pathplus, "extractdir")
		os.mkdir(DIR)

		with TarFile.open(tarname, encoding="iso8859-1") as tar:
			tarinfo = tar.getmember(dirtype)
			tar.extract(tarinfo, path=DIR)
			extracted = os.path.join(DIR, dirtype)
			assert os.path.getmtime(extracted) == tarinfo.mtime
			if sys.platform != "win32":
				assert os.stat(extracted).st_mode & 0o777 == 0o755

	def test_extractall_pathlike_name(self, tmp_pathplus: PathPlus):
		DIR = pathlib.Path(tmp_pathplus) / "extractall"
		with temp_dir(DIR), TarFile.open(tarname, encoding="iso8859-1") as tar:
			directories = [t for t in tar if t.isdir()]
			tar.extractall(DIR, directories)
			for tarinfo in directories:
				path = DIR / tarinfo.name
				assert os.path.getmtime(path) == tarinfo.mtime

	def test_extract_pathlike_name(self, tmp_pathplus: PathPlus):
		dirtype = "ustar/dirtype"
		DIR = pathlib.Path(tmp_pathplus) / "extractall"
		with temp_dir(DIR), TarFile.open(tarname, encoding="iso8859-1") as tar:
			tarinfo = tar.getmember(dirtype)
			tar.extract(tarinfo, path=DIR)
			extracted = DIR / dirtype
			assert os.path.getmtime(extracted) == tarinfo.mtime

	def test_init_close_fobj(self, tmp_pathplus: PathPlus):
		# Issue #7341: Close the internal file object in the TarFile
		# constructor in case of an error. For the test we rely on
		# the fact that opening an empty file raises a ReadError.
		empty = os.path.join(tmp_pathplus, "empty")
		with open(empty, "wb") as fobj:
			fobj.write(b"")

		try:
			tar = object.__new__(TarFile)
			try:
				tar.__init__(empty)
			except tarfile.ReadError:
				assert tar.fileobj.closed
			else:
				pytest.fail("ReadError not raised")
		finally:
			unlink(empty)

	def test_parallel_iteration(self, tmp_pathplus: PathPlus):
		# Issue #16601: Restarting iteration over tarfile continued
		# from where it left off.
		with TarFile.open(tmp_pathplus / self.tarname) as tar:
			for m1, m2 in zip(tar, tar):
				assert m1.offset == m2.offset
				assert m1.get_info() == m2.get_info()


class TestReadMisc(MiscReadTestBase):
	test_fail_comp = None


class TestReadMiscGzip(GzipTest, MiscReadTestBase):
	pass


class TestReadMiscBz2(Bz2Test, MiscReadTestBase):

	def requires_name_attribute(self):
		pytest.skip("BZ2File have no name attribute")


class TestReadMiscLzma(LzmaTest, MiscReadTestBase):

	def requires_name_attribute(self):
		pytest.skip("LZMAFile have no name attribute")


class TestReadStream(CommonReadTest):

	prefix = "r|"

	def test_read_through(self):
		# Issue #11224: A poorly designed _FileInFile.read() method
		# caused seeking errors with stream tar files.
		for tarinfo in self.tar:
			if not tarinfo.isreg():
				continue
			with self.tar.extractfile(tarinfo) as fobj:
				while True:
					try:
						buf = fobj.read(512)
					except tarfile.StreamError:
						pytest.fail("simple read-through using TarFile.extractfile() failed")
					if not buf:
						break

	def test_fileobj_regular_file(self):
		tarinfo = self.tar.next()  # get "regtype" (can't use getmember)
		with self.tar.extractfile(tarinfo) as fobj:
			data = fobj.read()
		assert len(data) == tarinfo.size, "regular file extraction failed"
		assert sha256sum(data) == sha256_regtype, "regular file extraction failed"

	def test_provoke_stream_error(self):
		tarinfos = self.tar.getmembers()
		with self.tar.extractfile(tarinfos[0]) as f:  # read the first member
			with pytest.raises(tarfile.StreamError):
				f.read()

	def test_compare_members(self):
		tar1 = TarFile.open(tarname, encoding="iso8859-1")
		try:
			tar2 = self.tar

			while True:
				t1 = tar1.next()
				t2 = tar2.next()
				if t1 is None:
					break
				assert t2 is not None, "stream.next() failed."

				if t2.islnk() or t2.issym():
					with pytest.raises(tarfile.StreamError):
						tar2.extractfile(t2)
					continue

				try:
					v1 = tar1.extractfile(t1)
				except FileNotFoundError:
					continue

				v2 = tar2.extractfile(t2)
				assert v2 is not None, "stream.extractfile() failed"
				assert v1.read() == v2.read(), "stream extraction failed"
		finally:
			tar1.close()


class TestGzipStreamRead(GzipTest, TestReadStream):
	pass


class TestBz2StreamRead(Bz2Test, TestReadStream):
	pass


class TestLzmaStreamRead(LzmaTest, TestReadStream):
	pass


class TestDetectRead(TarTest):

	prefix = "r:"

	def _testfunc_file(self, name, mode):
		tar = None
		try:
			tar = TarFile.open(name, mode)
		finally:
			if tar is not None:
				tar.close()

	def _testfunc_fileobj(self, name, mode):
		tar = None
		try:
			with open(name, "rb") as f:
				tar = TarFile.open(name, mode, fileobj=f)
		finally:
			if tar is not None:
				tar.close()

	def _test_modes(self, testfunc, tmpdir):
		if self.suffix:
			with pytest.raises(tarfile.ReadError):
				TarFile.open(tarname, mode="r:" + self.suffix)
			with pytest.raises(tarfile.ReadError):
				TarFile.open(tarname, mode="r|" + self.suffix)
			with pytest.raises(tarfile.ReadError):
				TarFile.open(tmpdir / self.tarname, mode="r:")
			with pytest.raises(tarfile.ReadError):
				TarFile.open(tmpdir / self.tarname, mode="r|")
		testfunc(tmpdir / self.tarname, 'r')
		testfunc(tmpdir / self.tarname, "r:" + self.suffix)
		testfunc(tmpdir / self.tarname, "r:*")
		testfunc(tmpdir / self.tarname, "r|" + self.suffix)
		testfunc(tmpdir / self.tarname, "r|*")

	def test_detect_file(self, tmp_pathplus: PathPlus):
		self._test_modes(self._testfunc_file, tmp_pathplus)

	def test_detect_fileobj(self, tmp_pathplus: PathPlus):
		self._test_modes(self._testfunc_fileobj, tmp_pathplus)


class TestGzipDetectRead(GzipTest, TestDetectRead):
	pass


class TestBz2DetectRead(Bz2Test, TestDetectRead):

	def test_detect_stream_bz2(self):
		# Originally, tarfile's stream detection looked for the string
		# "BZh91" at the start of the file. This is incorrect because
		# the '9' represents the blocksize (900,000 bytes). If the file was
		# compressed using another blocksize autodetection fails.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with open(tarname, "rb") as fobj:
				data = fobj.read()

			# Compress with blocksize 100,000 bytes, the file starts with "BZh11".
			with bz2.BZ2File(tmpname, "wb", compresslevel=1) as fobj:
				fobj.write(data)

			self._testfunc_file(tmpname, "r|*")


class TestLzmaDetectRead(LzmaTest, TestDetectRead):
	pass


class TestReadMember(ReadTest):

	def _test_member(self, tarinfo, chksum=None, **kwargs):
		if chksum is not None:
			with self.tar.extractfile(tarinfo) as f:
				assert sha256sum(f.read()) == chksum, f"wrong sha256sum for {tarinfo.name}"

		kwargs["mtime"] = 0o7606136617
		kwargs["uid"] = 1000
		kwargs["gid"] = 100
		if "old-v7" not in tarinfo.name:
			# V7 tar can't handle alphabetic owners.
			kwargs["uname"] = "tarfile"
			kwargs["gname"] = "tarfile"
		for k, v in kwargs.items():
			assert getattr(tarinfo, k) == v, f"wrong value in {k} field of {tarinfo.name}"

	def test_find_regtype(self):
		tarinfo = self.tar.getmember("ustar/regtype")
		self._test_member(tarinfo, size=7011, chksum=sha256_regtype)

	def test_find_conttype(self):
		tarinfo = self.tar.getmember("ustar/conttype")
		self._test_member(tarinfo, size=7011, chksum=sha256_regtype)

	def test_find_dirtype(self):
		tarinfo = self.tar.getmember("ustar/dirtype")
		self._test_member(tarinfo, size=0)

	def test_find_dirtype_with_size(self):
		tarinfo = self.tar.getmember("ustar/dirtype-with-size")
		self._test_member(tarinfo, size=255)

	def test_find_lnktype(self):
		tarinfo = self.tar.getmember("ustar/lnktype")
		self._test_member(tarinfo, size=0, linkname="ustar/regtype")

	def test_find_symtype(self):
		tarinfo = self.tar.getmember("ustar/symtype")
		self._test_member(tarinfo, size=0, linkname="regtype")

	def test_find_blktype(self):
		tarinfo = self.tar.getmember("ustar/blktype")
		self._test_member(tarinfo, size=0, devmajor=3, devminor=0)

	def test_find_chrtype(self):
		tarinfo = self.tar.getmember("ustar/chrtype")
		self._test_member(tarinfo, size=0, devmajor=1, devminor=3)

	def test_find_fifotype(self):
		tarinfo = self.tar.getmember("ustar/fifotype")
		self._test_member(tarinfo, size=0)

	def test_find_sparse(self):
		tarinfo = self.tar.getmember("ustar/sparse")
		self._test_member(tarinfo, size=86016, chksum=sha256_sparse)

	def test_find_gnusparse(self):
		tarinfo = self.tar.getmember("gnu/sparse")
		self._test_member(tarinfo, size=86016, chksum=sha256_sparse)

	def test_find_gnusparse_00(self):
		tarinfo = self.tar.getmember("gnu/sparse-0.0")
		self._test_member(tarinfo, size=86016, chksum=sha256_sparse)

	def test_find_gnusparse_01(self):
		tarinfo = self.tar.getmember("gnu/sparse-0.1")
		self._test_member(tarinfo, size=86016, chksum=sha256_sparse)

	def test_find_gnusparse_10(self):
		tarinfo = self.tar.getmember("gnu/sparse-1.0")
		self._test_member(tarinfo, size=86016, chksum=sha256_sparse)

	def test_find_umlauts(self):
		tarinfo = self.tar.getmember("ustar/umlauts-ÄÖÜäöüß")
		self._test_member(tarinfo, size=7011, chksum=sha256_regtype)

	def test_find_ustar_longname(self):
		name = "ustar/" + "12345/" * 39 + "1234567/longname"
		assert name in self.tar.getnames()

	def test_find_regtype_oldv7(self):
		tarinfo = self.tar.getmember("misc/regtype-old-v7")
		self._test_member(tarinfo, size=7011, chksum=sha256_regtype)

	def test_find_pax_umlauts(self, tmp_pathplus: PathPlus):
		self.tar.close()
		self.tar = TarFile.open(tmp_pathplus / self.tarname, mode=self.mode, encoding="iso8859-1")
		tarinfo = self.tar.getmember("pax/umlauts-ÄÖÜäöüß")
		self._test_member(tarinfo, size=7011, chksum=sha256_regtype)


class LongnameTest:

	def test_read_longname(self):
		# Test reading of longname (bug #1471427).
		longname = self.subdir + '/' + "123/" * 125 + "longname"
		try:
			tarinfo = self.tar.getmember(longname)
		except KeyError:
			pytest.fail("longname not found")
		assert tarinfo.type != tarfile.DIRTYPE, "read longname as dirtype"

	def test_read_longlink(self):
		longname = self.subdir + '/' + "123/" * 125 + "longname"
		longlink = self.subdir + '/' + "123/" * 125 + "longlink"
		try:
			tarinfo = self.tar.getmember(longlink)
		except KeyError:
			pytest.fail("longlink not found")
		assert tarinfo.linkname == longname, "linkname wrong"

	def test_truncated_longname(self):
		longname = self.subdir + '/' + "123/" * 125 + "longname"
		tarinfo = self.tar.getmember(longname)
		offset = tarinfo.offset
		self.tar.fileobj.seek(offset)
		fobj = io.BytesIO(self.tar.fileobj.read(3 * 512))
		with pytest.raises(tarfile.ReadError):
			TarFile.open(name="foo.tar", fileobj=fobj)

	def test_header_offset(self):
		# Test if the start offset of the TarInfo object includes
		# the preceding extended header.
		longname = self.subdir + '/' + "123/" * 125 + "longname"
		offset = self.tar.getmember(longname).offset
		with open(tarname, "rb") as fobj:
			fobj.seek(offset)
			tarinfo = tarfile.TarInfo.frombuf(fobj.read(512), "iso8859-1", "strict")
			assert tarinfo.type == self.longnametype


class TestReadGNU(LongnameTest, ReadTest):

	subdir = "gnu"
	longnametype = tarfile.GNUTYPE_LONGNAME

	# Since 3.2 tarfile is supposed to accurately restore sparse members and
	# produce files with holes. This is what we actually want to test here.
	# Unfortunately, not all platforms/filesystems support sparse files, and
	# even on platforms that do it is non-trivial to make reliable assertions
	# about holes in files. Therefore, we first do one basic test which works
	# an all platforms, and after that a test that will work only on
	# platforms/filesystems that prove to support sparse files.
	def _test_sparse_file(self, name, tmpdir: PathPlus):
		self.tar.extract(name, tmpdir)
		filename = os.path.join(tmpdir, name)
		with open(filename, "rb") as fobj:
			data = fobj.read()
		assert sha256sum(data) == sha256_sparse, f"wrong sha256sum for {name}"

		if self._fs_supports_holes(tmpdir):
			s = os.stat(filename)
			assert s.st_blocks * 512 < s.st_size

	def test_sparse_file_old(self, tmp_pathplus: PathPlus):
		self._test_sparse_file("gnu/sparse", tmp_pathplus)

	def test_sparse_file_00(self, tmp_pathplus: PathPlus):
		self._test_sparse_file("gnu/sparse-0.0", tmp_pathplus)

	def test_sparse_file_01(self, tmp_pathplus: PathPlus):
		self._test_sparse_file("gnu/sparse-0.1", tmp_pathplus)

	def test_sparse_file_10(self, tmp_pathplus: PathPlus):
		self._test_sparse_file("gnu/sparse-1.0", tmp_pathplus)

	@staticmethod
	def _fs_supports_holes(tmpdir: PathPlus):
		# Return True if the platform knows the st_blocks stat attribute and
		# uses st_blocks units of 512 bytes, and if the filesystem is able to
		# store holes of 4 KiB in files.
		#
		# The function returns False if page size is larger than 4 KiB.
		# For example, ppc64 uses pages of 64 KiB.
		if sys.platform.startswith("linux"):
			# Linux evidentially has 512 byte st_blocks units.
			name = os.path.join(tmpdir, "sparse-test")
			with open(name, "wb") as fobj:
				# Seek to "punch a hole" of 4 KiB
				fobj.seek(4096)
				fobj.write(b'x' * 4096)
				fobj.truncate()
			s = os.stat(name)
			unlink(name)
			return (s.st_blocks * 512 < s.st_size)
		else:
			return False


class TestReadPax(LongnameTest, ReadTest):

	subdir = "pax"
	longnametype = tarfile.XHDTYPE

	def test_pax_global_headers(self):
		tar = TarFile.open(tarname, encoding="iso8859-1")
		try:
			tarinfo = tar.getmember("pax/regtype1")
			assert tarinfo.uname == "foo"
			assert tarinfo.gname == "bar"
			assert tarinfo.pax_headers.get("VENDOR.umlauts") == "ÄÖÜäöüß"

			tarinfo = tar.getmember("pax/regtype2")
			assert tarinfo.uname == ''
			assert tarinfo.gname == "bar"
			assert tarinfo.pax_headers.get("VENDOR.umlauts") == "ÄÖÜäöüß"

			tarinfo = tar.getmember("pax/regtype3")
			assert tarinfo.uname == "tarfile"
			assert tarinfo.gname == "tarfile"
			assert tarinfo.pax_headers.get("VENDOR.umlauts") == "ÄÖÜäöüß"
		finally:
			tar.close()

	def test_pax_number_fields(self):
		# All following number fields are read from the pax header.
		tar = TarFile.open(tarname, encoding="iso8859-1")
		try:
			tarinfo = tar.getmember("pax/regtype4")
			assert tarinfo.size == 7011
			assert tarinfo.uid == 123
			assert tarinfo.gid == 123
			assert tarinfo.mtime == 1041808783.0
			assert type(tarinfo.mtime) is float  # pylint: disable=unidiomatic-typecheck
			assert float(tarinfo.pax_headers["atime"]) == 1041808783.0
			assert float(tarinfo.pax_headers["ctime"]) == 1041808783.0
		finally:
			tar.close()


class WriteTestBase(TarTest):
	# Put all write tests in here that are supposed to be tested
	# in all possible mode combinations.

	def test_fileobj_no_close(self):
		fobj = io.BytesIO()
		with TarFile.open(fileobj=fobj, mode=self.mode) as tar:
			tar.addfile(tarfile.TarInfo("foo"))
		assert not fobj.closed, "external fileobjs must never closed"
		# Issue #20238: Incomplete gzip output with mode="w:gz"
		data = fobj.getvalue()
		del tar
		gc_collect()
		assert not fobj.closed
		assert data == fobj.getvalue()

	def test_eof_marker(self):
		# Make sure an end of archive marker is written (two zero blocks).
		# tarfile insists on aligning archives to a 20 * 512 byte recordsize.
		# So, we create an archive that has exactly 10240 bytes without the
		# marker, and has 20480 bytes once the marker is written.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode) as tar:
				t = tarfile.TarInfo("foo")
				t.size = tarfile.RECORDSIZE - tarfile.BLOCKSIZE
				tar.addfile(t, io.BytesIO(b"a" * t.size))

			with self.open(tmpname, "rb") as fobj:
				assert len(fobj.read()) == tarfile.RECORDSIZE * 2


class TestWrite(WriteTestBase):

	prefix = "w:"

	def test_100_char_name(self):
		# The name field in a tar header stores strings of at most 100 chars.
		# If a string is shorter than 100 chars it has to be padded with '\0',
		# which implies that a string of exactly 100 chars is stored without
		# a trailing '\0'.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			name = "0123456789" * 10
			tar = TarFile.open(tmpname, self.mode)
			try:
				t = tarfile.TarInfo(name)
				tar.addfile(t)
			finally:
				tar.close()

			tar = TarFile.open(tmpname)
			try:
				assert tar.getnames()[0] == name, "failed to store 100 char filename"
			finally:
				tar.close()

	def test_tar_size(self):
		# Test for bug #1013882.
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tar = TarFile.open(tmpname, self.mode)
			try:
				path = os.path.join(tmpdir, "file")
				with open(path, "wb") as fobj:
					fobj.write(b"aaa")
				tar.add(path)
			finally:
				tar.close()
			assert os.path.getsize(tmpname) > 0, "tarfile is empty"

	# The test_*_size tests test for bug #1167128.
	def test_file_size(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tar = TarFile.open(tmpname, self.mode)
			try:
				path = os.path.join(tmpdir, "file")
				with open(path, "wb"):
					pass
				tarinfo = tar.gettarinfo(path)
				assert tarinfo.size == 0

				with open(path, "wb") as fobj:
					fobj.write(b"aaa")
				tarinfo = tar.gettarinfo(path)
				assert tarinfo.size == 3
			finally:
				tar.close()

	def test_directory_size(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			path = os.path.join(tmpdir, "directory")
			os.mkdir(path)
			try:
				tar = TarFile.open(tmpname, self.mode)
				try:
					tarinfo = tar.gettarinfo(path)
					assert tarinfo.size == 0
				finally:
					tar.close()
			finally:
				rmdir(path)

	def test_gettarinfo_pathlike_name(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode) as tar:
				path = pathlib.Path(tmpdir) / "file"
				with open(path, "wb") as fobj:
					fobj.write(b"aaa")
				tarinfo = tar.gettarinfo(path)
				tarinfo2 = tar.gettarinfo(os.fspath(path))
				assert isinstance(tarinfo.name, str)
				assert tarinfo.name == tarinfo2.name
				assert tarinfo.size == 3

	@pytest.mark.skipif(not hasattr(os, "link"), reason="Missing hardlink implementation")
	def test_link_size(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			link = os.path.join(tmpdir, "link")
			target = os.path.join(tmpdir, "link_target")
			with open(target, "wb") as fobj:
				fobj.write(b"aaa")
			try:
				os.link(target, link)
			except PermissionError as e:
				pytest.skip(f"os.link(): {e}")
			try:
				tar = TarFile.open(tmpname, self.mode)
				try:
					# Record the link target in the inodes list.
					tar.gettarinfo(target)
					tarinfo = tar.gettarinfo(link)
					assert tarinfo.size == 0
				finally:
					tar.close()
			finally:
				unlink(target)
				unlink(link)

	@skip_unless_symlink
	def test_symlink_size(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			path = os.path.join(tmp_pathplus, "symlink")
			os.symlink("link_target", path)
			try:
				tar = TarFile.open(tmpname, self.mode)
				try:
					tarinfo = tar.gettarinfo(path)
					assert tarinfo.size == 0
				finally:
					tar.close()
			finally:
				unlink(path)

	def test_add_self(self):
		# Test for #1257255.
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			dstname = os.path.abspath(tmpname)
			tar = TarFile.open(tmpname, self.mode)
			try:
				assert tar.name == dstname, "archive name must be absolute"
				tar.add(dstname)
				assert tar.getnames() == [], "added the archive to itself"

				with in_directory(tmpdir):
					tar.add(dstname)
				assert tar.getnames() == [], "added the archive to itself"
			finally:
				tar.close()

	def test_filter(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tempdir = os.path.join(tmpdir, "filter")
			os.mkdir(tempdir)
			try:
				for name in ("foo", "bar", "baz"):
					name = os.path.join(tempdir, name)
					create_empty_file(name)

				def filter(tarinfo):  # noqa: A001  # pylint: disable=redefined-builtin
					if os.path.basename(tarinfo.name) == "bar":
						return
					tarinfo.uid = 123
					tarinfo.uname = "foo"
					return tarinfo

				tar = TarFile.open(tmpname, self.mode, encoding="iso8859-1")
				try:
					tar.add(tempdir, arcname="empty_dir", filter=filter)
				finally:
					tar.close()

				# Verify that filter is a keyword-only argument
				with pytest.raises(TypeError):
					tar.add(tempdir, "empty_dir", True, None, filter)

				tar = TarFile.open(tmpname, 'r')
				try:
					for tarinfo in tar:
						assert tarinfo.uid == 123
						assert tarinfo.uname == "foo"
					assert len(tar.getmembers()) == 3
				finally:
					tar.close()
			finally:
				rmtree(tempdir)

	# Guarantee that stored pathnames are not modified. Don't
	# remove ./ or ../ or double slashes. Still make absolute
	# pathnames relative.
	# For details see bug #6054.
	def _test_pathname(self, path, cmp_path=None, dir=False):  # noqa: A002  # pylint: disable=redefined-builtin
		# Create a tarfile with an empty member named path
		# and compare the stored name with the original.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			foo = os.path.join(tmpdir, "foo")
			if not dir:
				create_empty_file(foo)
			else:
				os.mkdir(foo)

			tar = TarFile.open(tmpname, self.mode)
			try:
				tar.add(foo, arcname=path)
			finally:
				tar.close()

			tar = TarFile.open(tmpname, 'r')
			try:
				t = tar.next()
			finally:
				tar.close()

			if not dir:
				unlink(foo)
			else:
				rmdir(foo)

			assert t.name == (cmp_path or path.replace(os.sep, '/'))

	def test_pathnames(self):
		self._test_pathname("foo")
		self._test_pathname(os.path.join("foo", '.', "bar"))
		self._test_pathname(os.path.join("foo", "..", "bar"))
		self._test_pathname(os.path.join('.', "foo"))
		self._test_pathname(os.path.join('.', "foo", '.'))
		self._test_pathname(os.path.join('.', "foo", '.', "bar"))
		self._test_pathname(os.path.join('.', "foo", "..", "bar"))
		self._test_pathname(os.path.join('.', "foo", "..", "bar"))
		self._test_pathname(os.path.join("..", "foo"))
		self._test_pathname(os.path.join("..", "foo", ".."))
		self._test_pathname(os.path.join("..", "foo", '.', "bar"))
		self._test_pathname(os.path.join("..", "foo", "..", "bar"))

		self._test_pathname("foo" + os.sep + os.sep + "bar")
		self._test_pathname("foo" + os.sep + os.sep, "foo", dir=True)

	def test_abs_pathnames(self):
		if sys.platform == "win32":
			self._test_pathname("C:\\foo", "foo")
		else:
			self._test_pathname("/foo", "foo")
			self._test_pathname("///foo", "foo")

	def test_cwd(self, tmp_pathplus):
		tmpname = tmp_pathplus / "tmp.tar"

		# Test adding the current working directory.
		with in_directory(tmp_pathplus):
			tar = TarFile.open(tmpname, self.mode)
			try:
				tar.add('.')
			finally:
				tar.close()

			tar = TarFile.open(tmpname, 'r')
			try:
				for t in tar:
					if t.name != '.':
						assert t.name.startswith("./"), t.name
			finally:
				tar.close()

	def test_open_nonwritable_fileobj(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			for exctype in OSError, EOFError, RuntimeError:

				class BadFile(io.BytesIO):
					first = True

					def write(self, data):
						if self.first:
							self.first = False
							raise exctype

				f = BadFile()
				with pytest.raises(exctype):
					TarFile.open(
							tmpname, self.mode, fileobj=f, format=tarfile.PAX_FORMAT, pax_headers={"non": "empty"}
							)
				assert not f.closed


class TestGzipWrite(GzipTest, TestWrite):
	pass


class TestBz2Write(Bz2Test, TestWrite):
	pass


class TestLzmaWrite(LzmaTest, TestWrite):
	pass


class TestWriteStream(WriteTestBase):

	prefix = "w|"
	decompressor = None

	def test_stream_padding(self):
		# Test for bug #1543303.
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tar = TarFile.open(tmpname, self.mode)
			tar.close()
			if self.decompressor:
				dec = self.decompressor()
				with open(tmpname, "rb") as fobj:
					data = fobj.read()
				data = dec.decompress(data)
				assert not dec.unused_data, "found trailing data"
			else:
				with self.open(tmpname) as fobj:
					data = fobj.read()
			assert data.count(b"\0") == tarfile.RECORDSIZE, "incorrect zero padding"

	@pytest.mark.skipif(
			not (sys.platform != "win32" and hasattr(os, "umask")), reason="Missing umask implementation"
			)
	def test_file_mode(self):
		# Test for issue #8464: Create files with correct
		# permissions.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			if os.path.exists(tmpname):
				unlink(tmpname)

			original_umask = os.umask(0o022)
			try:
				tar = TarFile.open(tmpname, self.mode)
				tar.close()
				mode = os.stat(tmpname).st_mode & 0o777
				assert mode == 0o644, "wrong file permissions"
			finally:
				os.umask(original_umask)


class TestWriteStreamGzip(GzipTest, TestWriteStream):
	pass


class TestWriteStreamBz2(Bz2Test, TestWriteStream):
	decompressor = bz2.BZ2Decompressor if bz2 else None


class TestWriteStreamLzma(LzmaTest, TestWriteStream):
	decompressor = lzma.LZMADecompressor if lzma else None


class TestWriteGNU(unittest.TestCase):
	# This testcase checks for correct creation of GNU Longname
	# and Longlink extended headers (cp. bug #812325).

	def _length(self, s):
		blocks = len(s) // 512 + 1
		return blocks * 512

	def _calc_size(self, name, link=None):
		# Initial tar header
		count = 512

		if len(name) > tarfile.LENGTH_NAME:
			# GNU longname extended header + longname
			count += 512
			count += self._length(name)
		if link is not None and len(link) > tarfile.LENGTH_LINK:
			# GNU longlink extended header + longlink
			count += 512
			count += self._length(link)
		return count

	def _test(self, name, link=None):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tarinfo = tarfile.TarInfo(name)
			if link:
				tarinfo.linkname = link
				tarinfo.type = tarfile.LNKTYPE

			tar = TarFile.open(tmpname, 'w')
			try:
				tar.format = tarfile.GNU_FORMAT
				tar.addfile(tarinfo)

				v1 = self._calc_size(name, link)
				v2 = tar.offset
				assert v1 == v2, "GNU longname/longlink creation failed"
			finally:
				tar.close()

			tar = TarFile.open(tmpname)
			try:
				member = tar.next()
				assert member is not None, "unable to read longname member"
				assert tarinfo.name == member.name, "unable to read longname member"
				assert tarinfo.linkname == member.linkname, "unable to read longname member"
			finally:
				tar.close()

	def test_longname_1023(self):
		self._test(("longnam/" * 127) + "longnam")

	def test_longname_1024(self):
		self._test(("longnam/" * 127) + "longname")

	def test_longname_1025(self):
		self._test(("longnam/" * 127) + "longname_")

	def test_longlink_1023(self):
		self._test("name", ("longlnk/" * 127) + "longlnk")

	def test_longlink_1024(self):
		self._test("name", ("longlnk/" * 127) + "longlink")

	def test_longlink_1025(self):
		self._test("name", ("longlnk/" * 127) + "longlink_")

	def test_longnamelink_1023(self):
		self._test(("longnam/" * 127) + "longnam", ("longlnk/" * 127) + "longlnk")

	def test_longnamelink_1024(self):
		self._test(("longnam/" * 127) + "longname", ("longlnk/" * 127) + "longlink")

	def test_longnamelink_1025(self):
		self._test(("longnam/" * 127) + "longname_", ("longlnk/" * 127) + "longlink_")


class TestCreate(WriteTestBase):

	prefix = "x:"

	@pytest.fixture(autouse=True)
	def _filepath(self, tmp_pathplus):
		with open(tmp_pathplus / "spameggs42", "wb") as fobj:
			fobj.write(b"aaa")

	def test_create(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode) as tobj:
				tobj.add(str(tmp_pathplus / "spameggs42"))

			with self.taropen(tmpname) as tobj:
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]

	def test_create_existing(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode) as tobj:
				tobj.add(str(tmp_pathplus / "spameggs42"))

			with pytest.raises(FileExistsError):
				tobj = TarFile.open(tmpname, self.mode)

			with self.taropen(tmpname) as tobj:
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]

	def test_create_taropen(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with self.taropen(tmpname, 'x') as tobj:
				tobj.add(str(tmp_pathplus / "spameggs42"))

			with self.taropen(tmpname) as tobj:
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]

	def test_create_existing_taropen(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with self.taropen(tmpname, 'x') as tobj:
				tobj.add(str(tmp_pathplus / "spameggs42"))

			with pytest.raises(FileExistsError):
				with self.taropen(tmpname, 'x'):
					pass

			with self.taropen(tmpname) as tobj:
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]

	def test_create_pathlike_name(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(pathlib.Path(tmpname), self.mode) as tobj:
				assert isinstance(tobj.name, str)
				assert tobj.name == os.path.abspath(tmpname)
				tobj.add(pathlib.Path(tmp_pathplus / "spameggs42"))
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]

			with self.taropen(tmpname) as tobj:
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]

	def test_create_taropen_pathlike_name(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with self.taropen(pathlib.Path(tmpname), 'x') as tobj:
				assert isinstance(tobj.name, str)
				assert tobj.name == os.path.abspath(tmpname)
				tobj.add(pathlib.Path(tmp_pathplus / "spameggs42"))
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]

			with self.taropen(tmpname) as tobj:
				names = tobj.getnames()
			assert len(names) == 1
			assert "spameggs42" in names[0]


class TestCreateGzip(GzipTest, TestCreate):
	open = None  # noqa: A003  # pylint: disable=redefined-builtin

	def test_eof_marker(self):
		# Make sure an end of archive marker is written (two zero blocks).
		# tarfile insists on aligning archives to a 20 * 512 byte recordsize.
		# So, we create an archive that has exactly 10240 bytes without the
		# marker, and has 20480 bytes once the marker is written.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode) as tar:
				t = tarfile.TarInfo("foo")
				t.size = tarfile.RECORDSIZE - tarfile.BLOCKSIZE
				tar.addfile(t, io.BytesIO(b"a" * t.size))

			with gzip.GzipFile(tmpname, "rb") as fobj:
				assert len(fobj.read()) == tarfile.RECORDSIZE * 2


class TestCreateBz2(Bz2Test, TestCreate):
	open = None  # noqa: A003  # pylint: disable=redefined-builtin

	def test_eof_marker(self):
		# Make sure an end of archive marker is written (two zero blocks).
		# tarfile insists on aligning archives to a 20 * 512 byte recordsize.
		# So, we create an archive that has exactly 10240 bytes without the
		# marker, and has 20480 bytes once the marker is written.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode) as tar:
				t = tarfile.TarInfo("foo")
				t.size = tarfile.RECORDSIZE - tarfile.BLOCKSIZE
				tar.addfile(t, io.BytesIO(b"a" * t.size))

			with bz2.BZ2File(tmpname, "rb") as fobj:
				assert len(fobj.read()) == tarfile.RECORDSIZE * 2


class TestCreateLzma(LzmaTest, TestCreate):
	open = None  # noqa: A003  # pylint: disable=redefined-builtin

	def test_eof_marker(self):
		# Make sure an end of archive marker is written (two zero blocks).
		# tarfile insists on aligning archives to a 20 * 512 byte recordsize.
		# So, we create an archive that has exactly 10240 bytes without the
		# marker, and has 20480 bytes once the marker is written.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, self.mode) as tar:
				t = tarfile.TarInfo("foo")
				t.size = tarfile.RECORDSIZE - tarfile.BLOCKSIZE
				tar.addfile(t, io.BytesIO(b"a" * t.size))

			with lzma.LZMAFile(tmpname, "rb") as fobj:
				assert len(fobj.read()) == tarfile.RECORDSIZE * 2


class TestCreateeWithXMode(TestCreate):

	prefix = 'x'

	test_create_taropen = None
	test_create_existing_taropen = None


class TestWritePax(TestWriteGNU):

	def _test(self, name, link=None):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			# See GNUWriteTest.
			tarinfo = tarfile.TarInfo(name)
			if link:
				tarinfo.linkname = link
				tarinfo.type = tarfile.LNKTYPE

			tar = TarFile.open(tmpname, 'w', format=tarfile.PAX_FORMAT)
			try:
				tar.addfile(tarinfo)
			finally:
				tar.close()

			tar = TarFile.open(tmpname)
			try:
				if link:
					l = tar.getmembers()[0].linkname
					assert link == l, "PAX longlink creation failed"
				else:
					n = tar.getmembers()[0].name
					assert name == n, "PAX longname creation failed"
			finally:
				tar.close()

	def test_pax_global_header(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			pax_headers = {"foo": "bar", "uid": '0', "mtime": "1.23", "test": "äöü", "äöü": "test"}

			tar = TarFile.open(tmpname, 'w', format=tarfile.PAX_FORMAT, pax_headers=pax_headers)
			try:
				tar.addfile(tarfile.TarInfo("test"))
			finally:
				tar.close()

			# Test if the global header was written correctly.
			tar = TarFile.open(tmpname, encoding="iso8859-1")
			try:
				assert tar.pax_headers == pax_headers
				assert tar.getmembers()[0].pax_headers == pax_headers
				# Test if all the fields are strings.
				for key, val in tar.pax_headers.items():
					assert type(key) is not bytes  # pylint: disable=unidiomatic-typecheck
					assert type(val) is not bytes  # pylint: disable=unidiomatic-typecheck
					if key in tarfile.PAX_NUMBER_FIELDS:
						try:
							tarfile.PAX_NUMBER_FIELDS[key](val)
						except (TypeError, ValueError):
							pytest.fail("unable to convert pax header field")
			finally:
				tar.close()

	def test_pax_extended_header(self):
		# The fields from the pax header have priority over the
		# TarInfo.
		pax_headers = {"path": "foo", "uid": "123"}

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tar = TarFile.open(tmpname, 'w', format=tarfile.PAX_FORMAT, encoding="iso8859-1")
			try:
				t = tarfile.TarInfo()
				t.name = "äöü"  # non-ASCII
				t.uid = 8**8  # too large
				t.pax_headers = pax_headers
				tar.addfile(t)
			finally:
				tar.close()

			tar = TarFile.open(tmpname, encoding="iso8859-1")
			try:
				t = tar.getmembers()[0]
				assert t.pax_headers == pax_headers
				assert t.name == "foo"
				assert t.uid == 123
			finally:
				tar.close()


class UnicodeTest:

	format: int  # noqa: A003  # pylint: disable=redefined-builtin

	def test_iso8859_1_filename(self):
		self._test_unicode_filename("iso8859-1")

	def test_utf7_filename(self):
		self._test_unicode_filename("utf7")

	def test_utf8_filename(self):
		self._test_unicode_filename("utf-8")

	def _test_unicode_filename(self, encoding):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tar = TarFile.open(tmpname, 'w', format=self.format, encoding=encoding, errors="strict")
			try:
				name = "äöü"
				tar.addfile(tarfile.TarInfo(name))
			finally:
				tar.close()

			tar = TarFile.open(tmpname, encoding=encoding)
			try:
				assert tar.getmembers()[0].name == name
			finally:
				tar.close()

	def test_unicode_filename_error(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			tar = TarFile.open(tmpname, 'w', format=self.format, encoding="ascii", errors="strict")
			try:
				tarinfo = tarfile.TarInfo()

				tarinfo.name = "äöü"
				with pytest.raises(UnicodeError):
					tar.addfile(tarinfo)

				tarinfo.name = "foo"
				tarinfo.uname = "äöü"
				with pytest.raises(UnicodeError):
					tar.addfile(tarinfo)
			finally:
				tar.close()

	def test_unicode_argument(self):
		tar = TarFile.open(tarname, 'r', encoding="iso8859-1", errors="strict")
		try:
			for t in tar:
				assert type(t.name) is str  # pylint: disable=unidiomatic-typecheck
				assert type(t.linkname) is str  # pylint: disable=unidiomatic-typecheck
				assert type(t.uname) is str  # pylint: disable=unidiomatic-typecheck
				assert type(t.gname) is str  # pylint: disable=unidiomatic-typecheck
		finally:
			tar.close()

	def test_uname_unicode(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			t = tarfile.TarInfo("foo")
			t.uname = "äöü"
			t.gname = "äöü"

			tar = TarFile.open(tmpname, mode='w', format=self.format, encoding="iso8859-1")
			try:
				tar.addfile(t)
			finally:
				tar.close()

			tar = TarFile.open(tmpname, encoding="iso8859-1")
			try:
				t = tar.getmember("foo")
				assert t.uname == "äöü"
				assert t.gname == "äöü"

				if self.format != tarfile.PAX_FORMAT:
					tar.close()
					tar = TarFile.open(tmpname, encoding="ascii")
					t = tar.getmember("foo")
					assert t.uname == "\udce4\udcf6\udcfc"
					assert t.gname == "\udce4\udcf6\udcfc"
			finally:
				tar.close()


class TestUnicodeUstar(UnicodeTest):

	format = tarfile.USTAR_FORMAT  # noqa: A003  # pylint: disable=redefined-builtin

	# Test whether the utf-8 encoded version of a filename exceeds the 100
	# bytes name field limit (every occurrence of '\xff' will be expanded to 2
	# bytes).
	def test_unicode_name1(self):
		self._test_ustar_name("0123456789" * 10)
		self._test_ustar_name("0123456789" * 10 + '0', ValueError)
		self._test_ustar_name("0123456789" * 9 + "01234567ÿ")
		self._test_ustar_name("0123456789" * 9 + "012345678ÿ", ValueError)

	def test_unicode_name2(self):
		self._test_ustar_name("0123456789" * 9 + "012345ÿÿ")
		self._test_ustar_name("0123456789" * 9 + "0123456ÿÿ", ValueError)

	# Test whether the utf-8 encoded version of a filename exceeds the 155
	# bytes prefix + '/' + 100 bytes name limit.
	def test_unicode_longname1(self):
		self._test_ustar_name("0123456789" * 15 + "01234/" + "0123456789" * 10)
		self._test_ustar_name("0123456789" * 15 + "0123/4" + "0123456789" * 10, ValueError)
		self._test_ustar_name("0123456789" * 15 + "012ÿ/" + "0123456789" * 10)
		self._test_ustar_name("0123456789" * 15 + "0123ÿ/" + "0123456789" * 10, ValueError)

	def test_unicode_longname2(self):
		self._test_ustar_name("0123456789" * 15 + "01ÿ/2" + "0123456789" * 10, ValueError)
		self._test_ustar_name("0123456789" * 15 + "01ÿÿ/" + "0123456789" * 10, ValueError)

	def test_unicode_longname3(self):
		self._test_ustar_name("0123456789" * 15 + "01ÿÿ/2" + "0123456789" * 10, ValueError)
		self._test_ustar_name("0123456789" * 15 + "01234/" + "0123456789" * 9 + "01234567ÿ")
		self._test_ustar_name("0123456789" * 15 + "01234/" + "0123456789" * 9 + "012345678ÿ", ValueError)

	def test_unicode_longname4(self):
		self._test_ustar_name("0123456789" * 15 + "01234/" + "0123456789" * 9 + "012345ÿÿ")
		self._test_ustar_name("0123456789" * 15 + "01234/" + "0123456789" * 9 + "0123456ÿÿ", ValueError)

	def _test_ustar_name(self, name, exc=None):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, 'w', format=self.format, encoding="utf-8") as tar:
				t = tarfile.TarInfo(name)
				if exc is None:
					tar.addfile(t)
				else:
					with pytest.raises(exc):
						tar.addfile(t)

			if exc is None:
				with TarFile.open(tmpname, 'r', encoding="utf-8") as tar:
					for t in tar:
						assert name == t.name
						break

	# Test the same as above for the 100 bytes link field.
	def test_unicode_link1(self):
		self._test_ustar_link("0123456789" * 10)
		self._test_ustar_link("0123456789" * 10 + '0', ValueError)
		self._test_ustar_link("0123456789" * 9 + "01234567ÿ")
		self._test_ustar_link("0123456789" * 9 + "012345678ÿ", ValueError)

	def test_unicode_link2(self):
		self._test_ustar_link("0123456789" * 9 + "012345ÿÿ")
		self._test_ustar_link("0123456789" * 9 + "0123456ÿÿ", ValueError)

	def _test_ustar_link(self, name, exc=None):

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, 'w', format=self.format, encoding="utf-8") as tar:
				t = tarfile.TarInfo("foo")
				t.linkname = name
				if exc is None:
					tar.addfile(t)
				else:
					with pytest.raises(exc):
						tar.addfile(t)

			if exc is None:
				with TarFile.open(tmpname, 'r', encoding="utf-8") as tar:
					for t in tar:
						assert name == t.linkname
						break


class TestUnicodeGNU(UnicodeTest):

	format = tarfile.GNU_FORMAT  # noqa: A003  # pylint: disable=redefined-builtin

	def test_bad_pax_header(self):
		# Test for issue #8633. GNU tar <= 1.23 creates raw binary fields
		# without a hdrcharset=BINARY header.
		for encoding, name in (
			("utf-8", "pax/bad-pax-\udce4\udcf6\udcfc"),
			("iso8859-1", "pax/bad-pax-äöü"),):
			with TarFile.open(tarname, encoding=encoding, errors="surrogateescape") as tar:
				try:
					t = tar.getmember(name)
				except KeyError:
					pytest.fail("unable to read bad GNU tar pax header")


class TestUnicodePAX(UnicodeTest):

	format = tarfile.PAX_FORMAT  # noqa: A003  # pylint: disable=redefined-builtin

	# PAX_FORMAT ignores encoding in write mode.
	test_unicode_filename_error = None

	def test_binary_header(self):
		# Test a POSIX.1-2008 compatible header with a hdrcharset=BINARY field.
		for encoding, name in (
			("utf-8", "pax/hdrcharset-\udce4\udcf6\udcfc"),
			("iso8859-1", "pax/hdrcharset-äöü"),):
			with TarFile.open(tarname, encoding=encoding, errors="surrogateescape") as tar:
				try:
					t = tar.getmember(name)
				except KeyError:
					pytest.fail("unable to read POSIX.1-2008 binary header")


class AppendTestBase:
	# Test append mode (cp. patch #1652681).

	def _create_testtar(self, tmpdir, mode="w:"):
		with TarFile.open(tmpdir / tarname, encoding="iso8859-1") as src:
			t = src.getmember("ustar/regtype")
			t.name = "foo"
			with src.extractfile(t) as f:
				with TarFile.open(tmpdir / "tmp.tar", mode) as tar:
					tar.addfile(t, f)

	def test_append_compressed(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			self._create_testtar(tmpdir, "w:" + self.suffix)
			with pytest.raises(tarfile.ReadError):
				TarFile.open(tmpname, 'a')


class TestAppend(AppendTestBase):
	test_append_compressed = None

	def _add_testfile(self, tmpdir, fileobj=None):
		with TarFile.open(tmpdir / "tmp.tar", 'a', fileobj=fileobj) as tar:
			tar.addfile(tarfile.TarInfo("bar"))

	def _test(self, tmpdir, names=["bar"], fileobj=None):
		with TarFile.open(tmpdir / "tmp.tar", fileobj=fileobj) as tar:
			assert tar.getnames() == names

	def test_non_existing(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"
			self._add_testfile(tmpdir)
			self._test(tmpdir)

	def test_empty(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"
			TarFile.open(tmpname, "w:").close()
			self._add_testfile(tmpdir)
			self._test(tmpdir)

	def test_empty_fileobj(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			fobj = io.BytesIO(b"\0" * 1024)
			self._add_testfile(tmpdir, fobj)
			fobj.seek(0)
			self._test(tmpdir, fileobj=fobj)

	def test_fileobj(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			self._create_testtar(tmpdir)
			with open(tmpname, "rb") as fobj:
				data = fobj.read()
			fobj = io.BytesIO(data)
			self._add_testfile(tmpdir, fobj)
			fobj.seek(0)
			self._test(tmpdir, names=["foo", "bar"], fileobj=fobj)

	def test_existing(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			self._create_testtar(tmpdir)
			self._add_testfile(tmpdir)
			self._test(tmpdir, names=["foo", "bar"])

	# Append mode is supposed to fail if the tarfile to append to
	# does not end with a zero block.
	def _test_error(self, data, tmpdir):
		with open(tmpdir / "tmp.tar", "wb") as fobj:
			fobj.write(data)
		with pytest.raises(tarfile.ReadError):
			self._add_testfile(tmpdir)

	def test_null(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"
			self._test_error(b"", tmpdir)

	def test_incomplete(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"
			self._test_error(b"\0" * 13, tmpdir)

	def test_premature_eof(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"
			data = tarfile.TarInfo("foo").tobuf()
			self._test_error(data, tmpdir)

	def test_trailing_garbage(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			data = tarfile.TarInfo("foo").tobuf()
			self._test_error(data + b"\0" * 13, tmpdir)

	def test_invalid(self):
		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"
			self._test_error(b"a" * 512, tmpdir)


class TestGzipAppend(GzipTest, AppendTestBase):
	mode = 'w'


class TestBz2Append(Bz2Test, AppendTestBase):
	mode = 'w'


class TestLzmaAppend(LzmaTest, AppendTestBase):
	mode = 'w'


class TestLimits:

	def test_ustar_limits(self):
		# 100 char name
		tarinfo = tarfile.TarInfo("0123456789" * 10)
		tarinfo.tobuf(tarfile.USTAR_FORMAT)

		# 101 char name that cannot be stored
		tarinfo = tarfile.TarInfo("0123456789" * 10 + '0')
		with pytest.raises(ValueError, match="name is too long"):
			tarinfo.tobuf(tarfile.USTAR_FORMAT)

		# 256 char name with a slash at pos 156
		tarinfo = tarfile.TarInfo("123/" * 62 + "longname")
		tarinfo.tobuf(tarfile.USTAR_FORMAT)

		# 256 char name that cannot be stored
		tarinfo = tarfile.TarInfo("1234567/" * 31 + "longname")
		with pytest.raises(ValueError, match="name is too long"):
			tarinfo.tobuf(tarfile.USTAR_FORMAT)

		# 512 char name
		tarinfo = tarfile.TarInfo("123/" * 126 + "longname")
		with pytest.raises(ValueError, match="name is too long"):
			tarinfo.tobuf(tarfile.USTAR_FORMAT)

		# 512 char linkname
		tarinfo = tarfile.TarInfo("longlink")
		tarinfo.linkname = "123/" * 126 + "longname"
		with pytest.raises(ValueError, match="linkname is too long"):
			tarinfo.tobuf(tarfile.USTAR_FORMAT)

		# uid > 8 digits
		tarinfo = tarfile.TarInfo("name")
		tarinfo.uid = 0o10000000
		with pytest.raises(ValueError, match="overflow in number field"):
			tarinfo.tobuf(tarfile.USTAR_FORMAT)

	def test_gnu_limits(self):
		tarinfo = tarfile.TarInfo("123/" * 126 + "longname")
		tarinfo.tobuf(tarfile.GNU_FORMAT)

		tarinfo = tarfile.TarInfo("longlink")
		tarinfo.linkname = "123/" * 126 + "longname"
		tarinfo.tobuf(tarfile.GNU_FORMAT)

		# uid >= 256 ** 7
		tarinfo = tarfile.TarInfo("name")
		tarinfo.uid = 0o4000000000000000000
		with pytest.raises(ValueError, match="overflow in number field"):
			tarinfo.tobuf(tarfile.GNU_FORMAT)

	def test_pax_limits(self):
		tarinfo = tarfile.TarInfo("123/" * 126 + "longname")
		tarinfo.tobuf(tarfile.PAX_FORMAT)

		tarinfo = tarfile.TarInfo("longlink")
		tarinfo.linkname = "123/" * 126 + "longname"
		tarinfo.tobuf(tarfile.PAX_FORMAT)

		tarinfo = tarfile.TarInfo("name")
		tarinfo.uid = 0o4000000000000000000
		tarinfo.tobuf(tarfile.PAX_FORMAT)


class TestContextManager:

	def test_basic(self):
		with TarFile.open(tarname) as tar:
			assert not tar.closed, "closed inside runtime context"
		assert tar.closed, "context manager failed"

	def test_closed(self):
		# The __enter__() method is supposed to raise OSError
		# if the TarFile object is already closed.
		tar = TarFile.open(tarname)
		tar.close()
		with pytest.raises(OSError, match="TarFile is closed"):
			with tar:
				pass

	def test_exception(self):
		# Test if the OSError exception is passed through properly.
		with pytest.raises(Exception, match="^$") as exc, TarFile.open(tarname) as tar:
			raise OSError

		assert isinstance(exc.value, OSError), "wrong exception raised in context manager"
		assert tar.closed, "context manager failed"

	def test_no_eof(self):
		# __exit__() must not write end-of-archive blocks if an exception was raised.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with suppress(Exception):
				with TarFile.open(tmpname, 'w') as tar:
					raise Exception

			assert os.path.getsize(tmpname) == 0, "context manager wrote an end-of-archive block"
			assert tar.closed, "context manager failed"

	def test_eof(self):
		# __exit__() must write end-of-archive blocks, i.e. call
		# TarFile.close() if there was no error.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with TarFile.open(tmpname, 'w'):
				pass

			assert os.path.getsize(tmpname) != 0, "context manager wrote no end-of-archive block"

	def test_fileobj(self):
		# Test that __exit__() did not close the external file
		# object.

		with TemporaryPathPlus() as tmpdir:
			tmpname = tmpdir / "tmp.tar"

			with open(tmpname, "wb") as fobj:

				with suppress(Exception):
					with TarFile.open(fileobj=fobj, mode='w') as tar:
						raise Exception

				assert not fobj.closed, "external file object was closed"
				assert tar.closed, "context manager failed"


class TestBz2PartialRead(Bz2Test):
	# Issue5068: The _BZ2Proxy.read() method loops forever
	# on an empty or partial bzipped file.

	mode = 'r'

	def _test_partial_input(self, mode):

		class MyBytesIO(io.BytesIO):
			hit_eof = False

			def read(self, n):
				if self.hit_eof:
					raise AssertionError("infinite loop detected in TarFile.open()")
				self.hit_eof = self.tell() == len(self.getvalue())
				return super().read(n)

			def seek(self, *args):
				self.hit_eof = False
				return super().seek(*args)

		data = bz2.compress(tarfile.TarInfo("foo").tobuf())
		for x in range(len(data) + 1):
			try:
				TarFile.open(fileobj=MyBytesIO(data[:x]), mode=mode)
			except tarfile.ReadError:
				pass  # we have no interest in ReadErrors

	def test_partial_input(self):
		self._test_partial_input('r')

	def test_partial_input_bz2(self):
		self._test_partial_input("r:bz2")
