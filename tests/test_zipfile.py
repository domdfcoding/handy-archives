# From https://github.com/python/cpython/blob/main/Lib/test/test_zipfile.py
#  Licensed under the Python Software Foundation License Version 2.
#  Copyright © 2001-2020 Python Software Foundation. All rights reserved.
#  Copyright © 2000 BeOpen.com. All rights reserved.
#  Copyright © 1995-2000 Corporation for National Research Initiatives. All rights reserved.
#  Copyright © 1991-1995 Stichting Mathematisch Centrum. All rights reserved.
#
# type: ignore

# stdlib
import contextlib
import io
import itertools
import os
import pathlib
import random
import struct
import sys
import time
import unittest
import unittest.mock as mock
import zipfile
from tempfile import TemporaryFile
from test.support import findfile
from typing import Iterator, no_type_check

# 3rd party
import pytest
from coincidence import min_version
from domdf_python_tools.paths import PathPlus, TemporaryPathPlus

# this package
from handy_archives import ZipFile
from tests.utils import TESTFN, requires_bz2, requires_lzma, requires_zlib

try:
	# stdlib
	from test.support import rmtree, temp_cwd, unlink
except ImportError:
	# stdlib
	from test.support.os_helper import rmtree, temp_cwd, unlink

TESTFN2 = TESTFN + '2'
TESTFNDIR = TESTFN + 'd'
FIXEDTEST_SIZE = 1000

SMALL_TEST_DATA = [
		("_ziptest1", "1q2w3e4r5t"),
		("ziptest2dir/_ziptest2", "qawsedrftg"),
		("ziptest2dir/ziptest3dir/_ziptest3", "azsxdcfvgb"),
		("ziptest2dir/ziptest3dir/ziptest4dir/_ziptest3", "6y7u8i9o0p"),
		]


@pytest.fixture()
def testfn(tmp_pathplus: PathPlus):
	return tmp_pathplus / TESTFN


@pytest.fixture()
def testfn2(tmp_pathplus: PathPlus):
	return tmp_pathplus / TESTFN2


def get_files(tmpdir: PathPlus):
	yield str(tmpdir / TESTFN2)
	with TemporaryFile() as f:
		yield f
		assert f.closed is False
	with io.BytesIO() as f:
		yield f
		assert f.closed is False


class AbstractTestsWithSourceFile:
	compression: int

	@classmethod
	def setup_class(cls):
		cls.line_gen = [
				bytes(f"Zipfile test line {i:d}. random float: {random.random():f}\n", "ascii")
				for i in range(FIXEDTEST_SIZE)
				]
		cls.data = b''.join(cls.line_gen)

	def make_test_archive(self, f, tmpdir, compression, compresslevel=None):
		kwargs = {"compression": compression, "compresslevel": compresslevel}

		if sys.version_info < (3, 7):
			kwargs.pop("compresslevel")

		# Create the ZIP archive
		with ZipFile(f, 'w', **kwargs) as zipfp:
			zipfp.write(tmpdir / TESTFN, "another.name")
			zipfp.write(tmpdir / TESTFN, TESTFN)
			zipfp.writestr("strfile", self.data)
			with zipfp.open("written-open-w", mode='w') as fp:
				for line in self.line_gen:
					fp.write(line)

	def zip_test(self, f, tmpdir, compression, compresslevel=None):
		self.make_test_archive(f, tmpdir, compression, compresslevel)

		# Read the ZIP archive
		with ZipFile(f, 'r', compression) as zipfp:
			assert zipfp.read(TESTFN) == self.data
			assert zipfp.read("another.name") == self.data
			assert zipfp.read("strfile") == self.data

			# Print the ZIP directory
			fp = io.StringIO()
			zipfp.printdir(file=fp)
			directory = fp.getvalue()
			lines = directory.splitlines()
			assert len(lines) == 5  # Number of files + header

			assert "File Name" in lines[0]
			assert "Modified" in lines[0]
			assert "Size" in lines[0]

			fn, date, time_, size = lines[1].split()
			assert fn == "another.name"
			assert time.strptime(date, "%Y-%m-%d")
			assert time.strptime(time_, "%H:%M:%S")
			assert size == str(len(self.data))

			# Check the namelist
			names = zipfp.namelist()
			assert len(names) == 4
			assert TESTFN in names
			assert "another.name" in names
			assert "strfile" in names
			assert "written-open-w" in names

			# Check infolist
			infos = zipfp.infolist()
			names = [i.filename for i in infos]
			assert len(names) == 4
			assert TESTFN in names
			assert "another.name" in names
			assert "strfile" in names
			assert "written-open-w" in names
			for i in infos:
				assert i.file_size == len(self.data)

			# check getinfo
			for nm in (TESTFN, "another.name", "strfile", "written-open-w"):
				info = zipfp.getinfo(nm)
				assert info.filename == nm
				assert info.file_size == len(self.data)

			# Check that testzip doesn't raise an exception
			zipfp.testzip()

	def test_basic(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.zip_test(f, tmp_pathplus, self.compression)

	def zip_open_test(self, f, tmpdir, compression):
		self.make_test_archive(f, tmpdir, compression)

		# Read the ZIP archive
		with ZipFile(f, 'r', compression) as zipfp:
			zipdata1 = []
			with zipfp.open(TESTFN) as zipopen1:
				while True:
					read_data = zipopen1.read(256)
					if not read_data:
						break
					zipdata1.append(read_data)

			zipdata2 = []
			with zipfp.open("another.name") as zipopen2:
				while True:
					read_data = zipopen2.read(256)
					if not read_data:
						break
					zipdata2.append(read_data)

			assert b''.join(zipdata1) == self.data
			assert b''.join(zipdata2) == self.data

	def test_open(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.zip_open_test(f, tmp_pathplus, self.compression)

	def test_open_with_pathlike(self, tmp_pathplus: PathPlus, testfn: PathPlus, testfn2: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		self.zip_open_test(testfn2, tmp_pathplus, self.compression)
		with ZipFile(testfn2, 'r', self.compression) as zipfp:
			assert isinstance(zipfp.filename, str)

	def test_random_open(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r', self.compression) as zipfp:
				zipdata1 = []
				with zipfp.open(TESTFN) as zipopen1:
					while True:
						read_data = zipopen1.read(random.randint(1, 1024))
						if not read_data:
							break
						zipdata1.append(read_data)

				assert b''.join(zipdata1) == self.data

	def test_read1(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r') as zipfp, zipfp.open(TESTFN) as zipopen:
				zipdata = []
				while True:
					read_data = zipopen.read1(-1)
					if not read_data:
						break
					zipdata.append(read_data)

			assert b''.join(zipdata) == self.data

	def test_read1_10(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r') as zipfp, zipfp.open(TESTFN) as zipopen:
				zipdata = []
				while True:
					read_data = zipopen.read1(10)
					assert len(read_data) <= 10
					if not read_data:
						break
					zipdata.append(read_data)

			assert b''.join(zipdata) == self.data

	def test_readline_read(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# Issue #7610: calls to readline() interleaved with calls to read().
		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r') as zipfp, zipfp.open(TESTFN) as zipopen:
				data = b''
				while True:
					read = zipopen.readline()
					if not read:
						break
					data += read

					read = zipopen.read(100)
					if not read:
						break
					data += read

			assert data == self.data

	def test_readline(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r') as zipfp:
				with zipfp.open(TESTFN) as zipopen:
					for line in self.line_gen:
						linedata = zipopen.readline()
						assert linedata == line

	def test_readlines(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r') as zipfp:
				with zipfp.open(TESTFN) as zipopen:
					ziplines = zipopen.readlines()
				for line, zipline in zip(self.line_gen, ziplines):
					assert zipline == line

	def test_iterlines(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r') as zipfp:
				with zipfp.open(TESTFN) as zipopen:
					for line, zipline in zip(self.line_gen, zipopen):
						assert zipline == line

	def test_low_compression(self, testfn: PathPlus, testfn2: PathPlus):
		# Check for cases where compressed data is larger than original.

		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# Create the ZIP archive
		with ZipFile(testfn2, 'w', self.compression) as zipfp:
			zipfp.writestr("strfile", "12")

		# Get an open object for strfile
		with ZipFile(testfn2, 'r', self.compression) as zipfp:
			with zipfp.open("strfile") as openobj:
				assert openobj.read(1) == b'1'
				assert openobj.read(1) == b'2'

	def test_writestr_compression(self, testfn: PathPlus, testfn2: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		zipfp = ZipFile(testfn2, 'w')
		zipfp.writestr("b.txt", "hello world", compress_type=self.compression)
		info = zipfp.getinfo("b.txt")
		assert info.compress_type == self.compression

	@min_version(3.7)
	def test_writestr_compresslevel(self, testfn2: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		zipfp = ZipFile(testfn2, 'w', compresslevel=1)
		zipfp.writestr("a.txt", "hello world", compress_type=self.compression)
		zipfp.writestr("b.txt", "hello world", compress_type=self.compression, compresslevel=2)

		# Compression level follows the constructor.
		a_info = zipfp.getinfo("a.txt")
		assert a_info.compress_type == self.compression
		assert a_info._compresslevel == 1

		# Compression level is overridden.
		b_info = zipfp.getinfo("b.txt")
		assert b_info.compress_type == self.compression
		assert b_info._compresslevel == 2

	@min_version(3.9)
	def test_read_return_size(self, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# Issue #9837: ZipExtFile.read() shouldn't return more bytes
		# than requested.
		for test_size in (1, 4095, 4096, 4097, 16384):
			file_size = test_size + 1
			junk = random.randbytes(file_size)
			with ZipFile(io.BytesIO(), 'w', self.compression) as zipf:
				zipf.writestr("foo", junk)
				with zipf.open("foo", 'r') as fp:
					buf = fp.read(test_size)
					assert len(buf) == test_size

	def test_truncated_zipfile(self, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		fp = io.BytesIO()
		with ZipFile(fp, mode='w') as zipf:
			zipf.writestr("strfile", self.data, compress_type=self.compression)
			end_offset = fp.tell()
		zipfiledata = fp.getvalue()

		fp = io.BytesIO(zipfiledata)
		with ZipFile(fp) as zipf:
			with zipf.open("strfile") as zipopen:
				fp.truncate(end_offset - 20)
				with pytest.raises(EOFError):
					zipopen.read()

		fp = io.BytesIO(zipfiledata)
		with ZipFile(fp) as zipf:
			with zipf.open("strfile") as zipopen:
				fp.truncate(end_offset - 20)
				with pytest.raises(EOFError):  # noqa: PT012
					while zipopen.read(100):
						pass

		fp = io.BytesIO(zipfiledata)
		with ZipFile(fp) as zipf:
			with zipf.open("strfile") as zipopen:
				fp.truncate(end_offset - 20)
				with pytest.raises(EOFError):  # noqa: PT012
					while zipopen.read1(100):
						pass

	def test_repr(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		fname = "file.name"
		for f in get_files(tmp_pathplus):
			with ZipFile(f, 'w', self.compression) as zipfp:
				zipfp.write(testfn, fname)
				r = repr(zipfp)
				assert "mode='w'" in r

			with ZipFile(f, 'r') as zipfp:
				r = repr(zipfp)
				if isinstance(f, str):
					assert f"filename={f!r}" in r
				else:
					assert f"file={f!r}" in r
				assert "mode='r'" in r
				r = repr(zipfp.getinfo(fname))
				assert f"filename={fname!r}" in r
				assert "filemode=" in r
				assert "file_size=" in r
				if self.compression != zipfile.ZIP_STORED:
					assert "compress_type=" in r
					assert "compress_size=" in r
				with zipfp.open(fname) as zipopen:
					r = repr(zipopen)
					assert f"name={fname!r}" in r
					assert "mode='r'" in r
					if self.compression != zipfile.ZIP_STORED:
						assert "compress_type=" in r
				assert "[closed]" in repr(zipopen)
			assert "[closed]" in repr(zipfp)

	def test_compresslevel_basic(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.zip_test(f, tmp_pathplus, self.compression, compresslevel=9)

	@min_version(3.7)
	def test_per_file_compresslevel(self, testfn: PathPlus, testfn2: PathPlus):
		# Check that files within a Zip archive can have different compression levels.

		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with ZipFile(testfn2, 'w', compresslevel=1) as zipfp:
			zipfp.write(testfn, "compress_1")
			zipfp.write(testfn, "compress_9", compresslevel=9)
			one_info = zipfp.getinfo("compress_1")
			nine_info = zipfp.getinfo("compress_9")
			assert one_info._compresslevel == 1
			assert nine_info._compresslevel == 9

	@min_version(3.7)
	def test_writing_errors(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		class BrokenFile(io.BytesIO):

			def write(self, data):
				nonlocal count
				if count is not None:
					if count == stop:
						raise OSError
					count += 1
				super().write(data)

		stop = 0
		while True:
			testfile = BrokenFile()
			count = None
			with ZipFile(testfile, 'w', self.compression) as zipfp:
				with zipfp.open("file1", 'w') as f:
					f.write(b'data1')
				count = 0
				try:
					with zipfp.open("file2", 'w') as f:
						f.write(b'data2')
				except OSError:
					stop += 1
				else:
					break
				finally:
					count = None
			with ZipFile(io.BytesIO(testfile.getvalue())) as zipfp:
				assert zipfp.namelist() == ["file1"]
				assert zipfp.read("file1") == b'data1'

		with ZipFile(io.BytesIO(testfile.getvalue())) as zipfp:
			assert zipfp.namelist() == ["file1", "file2"]
			assert zipfp.read("file1") == b'data1'
			assert zipfp.read("file2") == b'data2'


class TestStoredTestsWithSourceFile(AbstractTestsWithSourceFile):
	compression = zipfile.ZIP_STORED
	test_low_compression = None

	def zip_test_writestr_permissions(self, f, tmpdir, compression):
		# Make sure that writestr and open(... mode='w') create files with
		# mode 0600, when they are passed a name rather than a ZipInfo
		# instance.

		self.make_test_archive(f, tmpdir, compression)
		with ZipFile(f, 'r') as zipfp:
			zinfo = zipfp.getinfo("strfile")
			assert zinfo.external_attr == 0o600 << 16

			zinfo2 = zipfp.getinfo("written-open-w")
			assert zinfo2.external_attr == 0o600 << 16

	def test_writestr_permissions(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.zip_test_writestr_permissions(f, tmp_pathplus, zipfile.ZIP_STORED)

	def test_absolute_arcnames(self, testfn: PathPlus, testfn2: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with ZipFile(testfn, 'w', zipfile.ZIP_STORED) as zipfp:
			zipfp.write(testfn, "/absolute")

		with ZipFile(testfn, 'r', zipfile.ZIP_STORED) as zipfp:
			assert zipfp.namelist() == ["absolute"]

	def test_append_to_zip_file(self, testfn: PathPlus, testfn2: PathPlus):
		# Test appending to an existing zipfile.

		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with ZipFile(testfn2, 'w', zipfile.ZIP_STORED) as zipfp:
			zipfp.write(testfn, TESTFN)

		with ZipFile(testfn2, 'a', zipfile.ZIP_STORED) as zipfp:
			zipfp.writestr("strfile", self.data)
			assert zipfp.namelist() == [TESTFN, "strfile"]

	def test_append_to_non_zip_file(self, testfn: PathPlus, testfn2: PathPlus):
		# Test appending to an existing file that is not a zipfile.

		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# NOTE: this test fails if len(d) < 22 because of the first
		# line "fpin.seek(-22, 2)" in _EndRecData
		data = b'I am not a ZipFile!' * 10
		with open(testfn2, "wb") as f:
			f.write(data)

		with ZipFile(testfn2, 'a', zipfile.ZIP_STORED) as zipfp:
			zipfp.write(testfn, TESTFN)

		with open(testfn2, "rb") as f:
			f.seek(len(data))
			with ZipFile(f, 'r') as zipfp:
				assert zipfp.namelist() == [TESTFN]
				assert zipfp.read(TESTFN) == self.data
		with open(testfn2, "rb") as f:
			assert f.read(len(data)) == data
			zipfiledata = f.read()
		with io.BytesIO(zipfiledata) as bio, ZipFile(bio) as zipfp:
			assert zipfp.namelist() == [TESTFN]
			assert zipfp.read(TESTFN) == self.data

	def test_read_concatenated_zip_file(self, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with io.BytesIO() as bio:
			with ZipFile(bio, 'w', zipfile.ZIP_STORED) as zipfp:
				zipfp.write(testfn, TESTFN)
			zipfiledata = bio.getvalue()
		data = b'I am not a ZipFile!' * 10
		with open(testfn, "wb") as f:
			f.write(data)
			f.write(zipfiledata)

		with ZipFile(testfn) as zipfp:
			assert zipfp.namelist() == [TESTFN]
			assert zipfp.read(TESTFN) == self.data

	def test_append_to_concatenated_zip_file(self, testfn: PathPlus, testfn2: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with io.BytesIO() as bio:
			with ZipFile(bio, 'w', zipfile.ZIP_STORED) as zipfp:
				zipfp.write(testfn, TESTFN)
			zipfiledata = bio.getvalue()
		data = b'I am not a ZipFile!' * 1000000
		with open(testfn2, "wb") as f:
			f.write(data)
			f.write(zipfiledata)

		with ZipFile(testfn2, 'a') as zipfp:
			assert zipfp.namelist() == [TESTFN]
			zipfp.writestr("strfile", self.data)

		with open(testfn2, "rb") as f:
			assert f.read(len(data)) == data
			zipfiledata = f.read()
		with io.BytesIO(zipfiledata) as bio, ZipFile(bio) as zipfp:
			assert zipfp.namelist() == [TESTFN, "strfile"]
			assert zipfp.read(TESTFN) == self.data
			assert zipfp.read("strfile") == self.data

	def test_ignores_newline_at_end(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with ZipFile(tmp_pathplus / TESTFN2, 'w', zipfile.ZIP_STORED) as zipfp:
			zipfp.write(testfn, TESTFN)
		with open(tmp_pathplus / TESTFN2, 'a', encoding="utf-8") as f:
			f.write("\r\n\00\00\00")
		with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
			assert isinstance(zipfp, ZipFile)

	def test_ignores_stuff_appended_past_comments(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with ZipFile(tmp_pathplus / TESTFN2, 'w', zipfile.ZIP_STORED) as zipfp:
			zipfp.comment = b"this is a comment"
			zipfp.write(testfn, TESTFN)
		with open(tmp_pathplus / TESTFN2, 'a', encoding="utf-8") as f:
			f.write("abcdef\r\n")
		with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
			assert isinstance(zipfp, ZipFile)
			assert zipfp.comment == b"this is a comment"

	def test_write_default_name(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# Check that calling ZipFile.write without arcname specified produces the expected result.

		with ZipFile(tmp_pathplus / TESTFN2, 'w') as zipfp:
			zipfp.write(testfn, TESTFN)
			with open(testfn, "rb") as f:
				assert zipfp.read(TESTFN) == f.read()

	@min_version(3.9)
	def test_io_on_closed_zipextfile(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		fname = "somefile.txt"
		with ZipFile(tmp_pathplus / TESTFN2, mode='w') as zipfp:
			zipfp.writestr(fname, "bogus")

		with ZipFile(tmp_pathplus / TESTFN2, mode='r') as zipfp:
			with zipfp.open(fname) as fid:
				fid.close()
				with pytest.raises(ValueError, match="read from closed file."):
					fid.read()
				with pytest.raises(ValueError, match="seek on closed file"):
					fid.seek(0)
				with pytest.raises(ValueError, match="tell on closed file"):
					fid.tell()
				with pytest.raises(ValueError, match="I/O operation on closed file"):
					fid.readable()
				with pytest.raises(ValueError, match="I/O operation on closed file"):
					fid.seekable()

	def test_write_to_readonly(self, tmp_pathplus: PathPlus, testfn: PathPlus, testfn2: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# Check that trying to call write() on a readonly ZipFile object raises a ValueError.
		with ZipFile(testfn2, mode='w') as zipfp:
			zipfp.writestr("somefile.txt", "bogus")

		with ZipFile(testfn2, mode='r') as zipfp:
			with pytest.raises(ValueError, match=r"write\(\) requires mode 'w', 'x', or 'a'"):
				zipfp.write(testfn)

		with ZipFile(testfn2, mode='r') as zipfp:
			with pytest.raises(ValueError, match=r"write\(\) requires mode 'w', 'x', or 'a'"):
				zipfp.open(TESTFN, mode='w')

	@min_version(3.8)
	def test_add_file_before_1980(self, tmp_pathplus: PathPlus, testfn: PathPlus, testfn2: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# Set atime and mtime to 1970-01-01
		os.utime(testfn, (0, 0))
		with ZipFile(tmp_pathplus / TESTFN2, 'w') as zipfp:
			with pytest.raises(ValueError, match="ZIP does not support timestamps before 1980"):
				zipfp.write(testfn, TESTFN)

		with ZipFile(tmp_pathplus / TESTFN2, 'w', strict_timestamps=False) as zipfp:
			zipfp.write(testfn, TESTFN)
			zinfo = zipfp.getinfo(TESTFN)
			assert zinfo.date_time == (1980, 1, 1, 0, 0, 0)

	@min_version(3.8)
	def test_add_file_after_2107(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		# Set atime and mtime to 2108-12-30
		ts = 4386268800
		try:
			time.localtime(ts)
		except OverflowError:
			pytest.skip(msg=f'time.localtime({ts}) raises OverflowError')
		try:
			os.utime(testfn, (ts, ts))
		except OverflowError:
			pytest.skip(msg="Host fs cannot set timestamp to required value.")

		mtime_ns = os.stat(tmp_pathplus / TESTFN).st_mtime_ns
		if mtime_ns != (4386268800 * 10**9):
			# XFS filesystem is limited to 32-bit timestamp, but the syscall
			# didn't fail. Moreover, there is a VFS bug which returns
			# a cached timestamp which is different than the value on disk.
			#
			# Test st_mtime_ns rather than st_mtime to avoid rounding issues.
			#
			# https://bugzilla.redhat.com/show_bug.cgi?id=1795576
			# https://bugs.python.org/issue39460#msg360952
			pytest.skip(f"Linux VFS/XFS kernel bug detected: mtime_ns={mtime_ns}")

		with ZipFile(tmp_pathplus / TESTFN2, 'w') as zipfp:
			with pytest.raises(struct.error):
				zipfp.write(tmp_pathplus / TESTFN)

		with ZipFile(tmp_pathplus / TESTFN2, 'w', strict_timestamps=False) as zipfp:
			zipfp.write(testfn, TESTFN)
			zinfo = zipfp.getinfo(TESTFN)
			assert zinfo.date_time == (2107, 12, 31, 23, 59, 59)


@requires_zlib()
class TestDeflateTestsWithSourceFile(AbstractTestsWithSourceFile):
	compression = zipfile.ZIP_DEFLATED

	def test_per_file_compression(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Check that files within a Zip archive can have different compression options.

		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		with ZipFile(tmp_pathplus / TESTFN2, 'w') as zipfp:
			zipfp.write(testfn, "storeme", zipfile.ZIP_STORED)
			zipfp.write(testfn, "deflateme", zipfile.ZIP_DEFLATED)
			sinfo = zipfp.getinfo("storeme")
			dinfo = zipfp.getinfo("deflateme")
			assert sinfo.compress_type == zipfile.ZIP_STORED
			assert dinfo.compress_type == zipfile.ZIP_DEFLATED


@requires_bz2()
class TestBzip2TestsWithSourceFile(AbstractTestsWithSourceFile):
	compression = zipfile.ZIP_BZIP2


@requires_lzma()
class TestLzmaTestsWithSourceFile(AbstractTestsWithSourceFile):
	compression = zipfile.ZIP_LZMA


@pytest.fixture()
def zip64_smallfiles(tmp_pathplus: PathPlus, testfn: PathPlus) -> PathPlus:
	_limit = zipfile.ZIP64_LIMIT
	_filecount_limit = zipfile.ZIP_FILECOUNT_LIMIT
	zipfile.ZIP64_LIMIT = 1000
	zipfile.ZIP_FILECOUNT_LIMIT = 9

	line_gen = (bytes(f"Test of zipfile line {i:d}.", "ascii") for i in range(0, FIXEDTEST_SIZE))

	# Make a source file with some lines
	with open(testfn, "wb") as fp:
		fp.write(b'\n'.join(line_gen))

	try:
		yield tmp_pathplus / TESTFN

	finally:
		zipfile.ZIP64_LIMIT = _limit
		zipfile.ZIP_FILECOUNT_LIMIT = _filecount_limit


class AbstractTestZip64InSmallFiles:
	# These tests test the ZIP64 functionality without using large files,
	# see test_zipfile64 for proper tests.

	compression: int

	@classmethod
	def setup_class(cls):
		line_gen = (bytes(f"Test of zipfile line {i:d}.", "ascii") for i in range(0, FIXEDTEST_SIZE))
		cls.data = b'\n'.join(line_gen)

	def zip_test(self, f, tmpdir, compression):
		# Create the ZIP archive
		with ZipFile(f, 'w', compression, allowZip64=True) as zipfp:
			zipfp.write(tmpdir / TESTFN, "another.name")
			zipfp.write(tmpdir / TESTFN, TESTFN)
			zipfp.writestr("strfile", self.data)

		# Read the ZIP archive
		with ZipFile(f, 'r', compression) as zipfp:
			assert zipfp.read(TESTFN) == self.data
			assert zipfp.read("another.name") == self.data
			assert zipfp.read("strfile") == self.data

			# Print the ZIP directory
			fp = io.StringIO()
			zipfp.printdir(fp)

			directory = fp.getvalue()
			lines = directory.splitlines()
			assert len(lines) == 4  # Number of files + header

			assert "File Name" in lines[0]
			assert "Modified" in lines[0]
			assert "Size" in lines[0]

			fn, date, time_, size = lines[1].split()
			assert fn == "another.name"
			assert time.strptime(date, "%Y-%m-%d")
			assert time.strptime(time_, "%H:%M:%S")
			assert size == str(len(self.data))

			# Check the namelist
			names = zipfp.namelist()
			assert len(names) == 3
			assert TESTFN in names
			assert "another.name" in names
			assert "strfile" in names

			# Check infolist
			infos = zipfp.infolist()
			names = [i.filename for i in infos]
			assert len(names) == 3
			assert TESTFN in names
			assert "another.name" in names
			assert "strfile" in names
			for i in infos:
				assert i.file_size == len(self.data)

			# check getinfo
			for nm in (TESTFN, "another.name", "strfile"):
				info = zipfp.getinfo(nm)
				assert info.filename == nm
				assert info.file_size == len(self.data)

			# Check that testzip doesn't raise an exception
			zipfp.testzip()

	def test_basic(self, tmp_pathplus: PathPlus, zip64_smallfiles):

		for f in get_files(tmp_pathplus):
			self.zip_test(f, tmp_pathplus, self.compression)

	def test_too_many_files(self, zip64_smallfiles):

		# This test checks that more than 64k files can be added to an archive,
		# and that the resulting archive can be read properly by ZipFile
		zipf = ZipFile(zip64_smallfiles, 'w', self.compression, allowZip64=True)
		zipf.debug = 100
		numfiles = 15
		for i in range(numfiles):
			zipf.writestr(f"foo{i:08d}", f"{i ** 3 % 57:d}")
		assert len(zipf.namelist()) == numfiles
		zipf.close()

		zipf2 = ZipFile(zip64_smallfiles, 'r', self.compression)
		assert len(zipf2.namelist()) == numfiles
		for i in range(numfiles):
			content = zipf2.read(f"foo{i:08d}").decode("ascii")
			assert content == f"{i ** 3 % 57:d}"
		zipf2.close()

	def test_too_many_files_append(self, zip64_smallfiles):
		zipf = ZipFile(zip64_smallfiles, 'w', self.compression, allowZip64=False)
		zipf.debug = 100
		numfiles = 9
		for i in range(numfiles):
			zipf.writestr(f"foo{i:08d}", "%d" % (i**3 % 57))
		assert len(zipf.namelist()) == numfiles
		with pytest.raises(zipfile.LargeZipFile):
			zipf.writestr(f"foo{numfiles:08d}", b'')
		assert len(zipf.namelist()) == numfiles
		zipf.close()

		zipf = ZipFile(zip64_smallfiles, 'a', self.compression, allowZip64=False)
		zipf.debug = 100
		assert len(zipf.namelist()) == numfiles
		with pytest.raises(zipfile.LargeZipFile):
			zipf.writestr(f"foo{numfiles:08d}", b'')
		assert len(zipf.namelist()) == numfiles
		zipf.close()

		zipf = ZipFile(zip64_smallfiles, 'a', self.compression, allowZip64=True)
		zipf.debug = 100
		assert len(zipf.namelist()) == numfiles
		numfiles2 = 15
		for i in range(numfiles, numfiles2):
			zipf.writestr(f"foo{i:08d}", "%d" % (i**3 % 57))
		assert len(zipf.namelist()) == numfiles2
		zipf.close()

		zipf2 = ZipFile(zip64_smallfiles, 'r', self.compression)
		assert len(zipf2.namelist()) == numfiles2
		for i in range(numfiles2):
			content = zipf2.read(f"foo{i:08d}").decode("ascii")
			assert content == f"{i ** 3 % 57:d}"
		zipf2.close()


class TestStoredTestZip64InSmallFiles(AbstractTestZip64InSmallFiles):
	compression = zipfile.ZIP_STORED

	def large_file_exception_test(self, f, compression, filename):
		with ZipFile(f, 'w', compression, allowZip64=False) as zipfp:
			with pytest.raises(zipfile.LargeZipFile):
				zipfp.write(filename, "another.name")

	def large_file_exception_test2(self, f, compression):
		with ZipFile(f, 'w', compression, allowZip64=False) as zipfp:
			with pytest.raises(zipfile.LargeZipFile):
				zipfp.writestr("another.name", self.data)

	def test_large_file_exception(self, zip64_smallfiles, tmp_pathplus: PathPlus):
		for f in get_files(tmp_pathplus):
			self.large_file_exception_test(f, zipfile.ZIP_STORED, zip64_smallfiles)
			self.large_file_exception_test2(f, zipfile.ZIP_STORED)

	def test_absolute_arcnames(self, tmp_pathplus: PathPlus, zip64_smallfiles):
		with ZipFile(tmp_pathplus / TESTFN2, 'w', zipfile.ZIP_STORED, allowZip64=True) as zipfp:
			zipfp.write(zip64_smallfiles, "/absolute")

		with ZipFile(tmp_pathplus / TESTFN2, 'r', zipfile.ZIP_STORED) as zipfp:
			assert zipfp.namelist() == ["absolute"]

	def test_append(self, tmp_pathplus: PathPlus):

		# Test that appending to the Zip64 archive doesn't change
		# extra fields of existing entries.
		with ZipFile(tmp_pathplus / TESTFN2, 'w', allowZip64=True) as zipfp:
			zipfp.writestr("strfile", self.data)
		with ZipFile(tmp_pathplus / TESTFN2, 'r', allowZip64=True) as zipfp:
			zinfo = zipfp.getinfo("strfile")
			extra = zinfo.extra
		with ZipFile(tmp_pathplus / TESTFN2, 'a', allowZip64=True) as zipfp:
			zipfp.writestr("strfile2", self.data)
		with ZipFile(tmp_pathplus / TESTFN2, 'r', allowZip64=True) as zipfp:
			zinfo = zipfp.getinfo("strfile")
			assert zinfo.extra == extra

	def make_zip64_file(
			self,
			file_size_64_set=False,
			file_size_extra=False,
			compress_size_64_set=False,
			compress_size_extra=False,
			header_offset_64_set=False,
			header_offset_extra=False,
			):
		"""Generate bytes sequence for a zip with (incomplete) zip64 data.

		The actual values (not the zip 64 0xffffffff values) stored in the file
		are:
		file_size: 8
		compress_size: 8
		header_offset: 0
		"""
		actual_size = 8
		actual_header_offset = 0
		local_zip64_fields = []
		central_zip64_fields = []

		file_size = actual_size
		if file_size_64_set:
			file_size = 0xffffffff
			if file_size_extra:
				local_zip64_fields.append(actual_size)
				central_zip64_fields.append(actual_size)
		file_size = struct.pack("<L", file_size)

		compress_size = actual_size
		if compress_size_64_set:
			compress_size = 0xffffffff
			if compress_size_extra:
				local_zip64_fields.append(actual_size)
				central_zip64_fields.append(actual_size)
		compress_size = struct.pack("<L", compress_size)

		header_offset = actual_header_offset
		if header_offset_64_set:
			header_offset = 0xffffffff
			if header_offset_extra:
				central_zip64_fields.append(actual_header_offset)
		header_offset = struct.pack("<L", header_offset)

		local_extra = struct.pack(
				"<HH" + 'Q' * len(local_zip64_fields), 0x0001, 8 * len(local_zip64_fields), *local_zip64_fields
				)

		central_extra = struct.pack(
				"<HH" + 'Q' * len(central_zip64_fields),
				0x0001,
				8 * len(central_zip64_fields),
				*central_zip64_fields
				)

		central_dir_size = struct.pack("<Q", 58 + 8 * len(central_zip64_fields))
		offset_to_central_dir = struct.pack("<Q", 50 + 8 * len(local_zip64_fields))

		local_extra_length = struct.pack("<H", 4 + 8 * len(local_zip64_fields))
		central_extra_length = struct.pack("<H", 4 + 8 * len(central_zip64_fields))

		filename = b"test.txt"
		content = b"test1234"
		filename_length = struct.pack("<H", len(filename))
		zip64_contents = (
				# Local file header
				b"PK\x03\x04\x14\x00\x00\x00\x00\x00\x00\x00!\x00\x9e%\xf5\xaf" + compress_size + file_size
				+ filename_length + local_extra_length + filename + local_extra + content
				# Central directory:
				+ b"PK\x01\x02-\x03-\x00\x00\x00\x00\x00\x00\x00!\x00\x9e%\xf5\xaf" + compress_size + file_size
				+ filename_length + central_extra_length + b"\x00\x00\x00\x00\x00\x00\x00\x00\x80\x01"
				+ header_offset + filename + central_extra
				# Zip64 end of central directory
				+ b"PK\x06\x06,\x00\x00\x00\x00\x00\x00\x00-\x00-"
				+ b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00"
				+ b"\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00" + central_dir_size + offset_to_central_dir
				# Zip64 end of central directory locator
				+ b"PK\x06\x07\x00\x00\x00\x00l\x00\x00\x00\x00\x00\x00\x00\x01" + b"\x00\x00\x00"
				# end of central directory
				+ b"PK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x00:\x00\x00\x002\x00" + b"\x00\x00\x00\x00"
				)
		return zip64_contents

	@min_version(3.7)
	def test_bad_zip64_extra(self, zip64_smallfiles):
		# zip64 file size present, no fields in extra, expecting one, equals
		# missing file size.
		missing_file_size_extra = self.make_zip64_file(file_size_64_set=True)
		with pytest.raises(zipfile.BadZipFile) as e:
			ZipFile(io.BytesIO(missing_file_size_extra))
		assert "file size" in str(e.value).lower()

		# zip64 file size present, zip64 compress size present, one field in
		# extra, expecting two, equals missing compress size.
		missing_compress_size_extra = self.make_zip64_file(
				file_size_64_set=True,
				file_size_extra=True,
				compress_size_64_set=True,
				)
		with pytest.raises(zipfile.BadZipFile) as e:
			ZipFile(io.BytesIO(missing_compress_size_extra))
		assert "compress size" in str(e.value).lower()

		# zip64 compress size present, no fields in extra, expecting one,
		# equals missing compress size.
		missing_compress_size_extra = self.make_zip64_file(compress_size_64_set=True, )
		with pytest.raises(zipfile.BadZipFile) as e:
			ZipFile(io.BytesIO(missing_compress_size_extra))
		assert "compress size" in str(e.value).lower()

		# zip64 file size present, zip64 compress size present, zip64 header
		# offset present, two fields in extra, expecting three, equals missing
		# header offset
		missing_header_offset_extra = self.make_zip64_file(
				file_size_64_set=True,
				file_size_extra=True,
				compress_size_64_set=True,
				compress_size_extra=True,
				header_offset_64_set=True,
				)
		with pytest.raises(zipfile.BadZipFile) as e:
			ZipFile(io.BytesIO(missing_header_offset_extra))
		assert "header offset" in str(e.value).lower()

		# zip64 compress size present, zip64 header offset present, one field
		# in extra, expecting two, equals missing header offset
		missing_header_offset_extra = self.make_zip64_file(
				file_size_64_set=False,
				compress_size_64_set=True,
				compress_size_extra=True,
				header_offset_64_set=True,
				)
		with pytest.raises(zipfile.BadZipFile) as e:
			ZipFile(io.BytesIO(missing_header_offset_extra))
		assert "header offset" in str(e.value).lower()

		# zip64 file size present, zip64 header offset present, one field in
		# extra, expecting two, equals missing header offset
		missing_header_offset_extra = self.make_zip64_file(
				file_size_64_set=True,
				file_size_extra=True,
				compress_size_64_set=False,
				header_offset_64_set=True,
				)
		with pytest.raises(zipfile.BadZipFile) as e:
			ZipFile(io.BytesIO(missing_header_offset_extra))
		assert "header offset" in str(e.value).lower()

		# zip64 header offset present, no fields in extra, expecting one,
		# equals missing header offset
		missing_header_offset_extra = self.make_zip64_file(
				file_size_64_set=False,
				compress_size_64_set=False,
				header_offset_64_set=True,
				)
		with pytest.raises(zipfile.BadZipFile) as e:
			ZipFile(io.BytesIO(missing_header_offset_extra))
		assert "header offset" in str(e.value).lower()

	def test_generated_valid_zip64_extra(self, zip64_smallfiles):

		# These values are what is set in the make_zip64_file method.
		expected_file_size = 8
		expected_compress_size = 8
		expected_header_offset = 0
		expected_content = b"test1234"

		# Loop through the various valid combinations of zip64 masks
		# present and extra fields present.
		params = (
				{"file_size_64_set": True, "file_size_extra": True},
				{"compress_size_64_set": True, "compress_size_extra": True},
				{"header_offset_64_set": True, "header_offset_extra": True},
				)

		for r in range(1, len(params) + 1):
			for combo in itertools.combinations(params, r):
				kwargs = {}
				for c in combo:
					kwargs.update(c)
				with ZipFile(io.BytesIO(self.make_zip64_file(**kwargs))) as zf:
					zinfo = zf.infolist()[0]
					assert zinfo.file_size == expected_file_size
					assert zinfo.compress_size == expected_compress_size
					assert zinfo.header_offset == expected_header_offset
					assert zf.read(zinfo) == expected_content


@requires_zlib()
class TestDeflateTestZip64InSmallFiles(AbstractTestZip64InSmallFiles):
	compression = zipfile.ZIP_DEFLATED


@requires_bz2()
class TestBzip2TestZip64InSmallFiles(AbstractTestZip64InSmallFiles):
	compression = zipfile.ZIP_BZIP2


@requires_lzma()
class TestLzmaTestZip64InSmallFiles(AbstractTestZip64InSmallFiles):
	compression = zipfile.ZIP_LZMA


class AbstractWriterTests:

	def test_close_after_close(self, tmp_pathplus: PathPlus):
		data = b'content'
		with ZipFile(tmp_pathplus / TESTFN2, 'w', self.compression) as zipf:
			w = zipf.open("test", 'w')
			w.write(data)
			w.close()
			assert w.closed
			w.close()
			assert w.closed
			assert zipf.read("test") == data

	def test_write_after_close(self, tmp_pathplus: PathPlus):
		data = b'content'
		with ZipFile(tmp_pathplus / TESTFN2, 'w', self.compression) as zipf:
			w = zipf.open("test", 'w')
			w.write(data)
			w.close()
			assert w.closed
			with pytest.raises(ValueError, match="I/O operation on closed file."):
				w.write(b'')
			assert zipf.read("test") == data


class TestStoredWriter(AbstractWriterTests):
	compression = zipfile.ZIP_STORED


@requires_zlib()
class TestDeflateWriter(AbstractWriterTests):
	compression = zipfile.ZIP_DEFLATED


@requires_bz2()
class TestBzip2Writer(AbstractWriterTests):
	compression = zipfile.ZIP_BZIP2


@requires_lzma()
class TestLzmaWriter(AbstractWriterTests):
	compression = zipfile.ZIP_LZMA


class TestExtract:

	def make_test_file(self, tmpdir):
		with ZipFile(tmpdir / TESTFN2, 'w', zipfile.ZIP_STORED) as zipfp:
			for fpath, fdata in SMALL_TEST_DATA:
				zipfp.writestr(fpath, fdata)

	def test_extract(self, tmp_pathplus: PathPlus):
		with temp_cwd():
			self.make_test_file(tmp_pathplus)
			with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
				for fpath, fdata in SMALL_TEST_DATA:
					writtenfile = zipfp.extract(fpath)

					# make sure it was written to the right place
					correctfile = os.path.join(os.getcwd(), fpath)
					correctfile = os.path.normpath(correctfile)

					assert writtenfile == correctfile

					# make sure correct data is in correct file
					with open(writtenfile, "rb") as f:
						assert fdata.encode() == f.read()

					unlink(writtenfile)

	def _test_extract_with_target(self, target, tmpdir):
		self.make_test_file(tmpdir)
		with ZipFile(tmpdir / TESTFN2, 'r') as zipfp:
			for fpath, fdata in SMALL_TEST_DATA:
				writtenfile = zipfp.extract(fpath, target)

				# make sure it was written to the right place
				correctfile = os.path.join(target, fpath)
				correctfile = os.path.normpath(correctfile)
				assert os.path.samefile(writtenfile, correctfile), (writtenfile, target)

				# make sure correct data is in correct file
				with open(writtenfile, "rb") as f:
					assert fdata.encode() == f.read()

				unlink(writtenfile)

	def test_extract_with_target(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as extdir:
			self._test_extract_with_target(extdir, tmp_pathplus)

	def test_extract_with_target_pathlike(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as extdir:
			self._test_extract_with_target(pathlib.Path(extdir), tmp_pathplus)

	def test_extract_all(self, tmp_pathplus: PathPlus):
		with temp_cwd():
			self.make_test_file(tmp_pathplus)
			with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
				zipfp.extractall()
				for fpath, fdata in SMALL_TEST_DATA:
					outfile = os.path.join(os.getcwd(), fpath)

					with open(outfile, "rb") as f:
						assert fdata.encode() == f.read()

					unlink(outfile)

	def _test_extract_all_with_target(self, target, tmpdir):
		self.make_test_file(tmpdir)
		with ZipFile(tmpdir / TESTFN2, 'r') as zipfp:
			zipfp.extractall(target)
			for fpath, fdata in SMALL_TEST_DATA:
				outfile = os.path.join(target, fpath)

				with open(outfile, "rb") as f:
					assert fdata.encode() == f.read()

				unlink(outfile)

	def test_extract_all_with_target(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as extdir:
			self._test_extract_all_with_target(str(extdir), tmp_pathplus)

	def test_extract_all_with_target_pathlike(self, tmp_pathplus: PathPlus):
		with TemporaryPathPlus() as extdir:
			self._test_extract_all_with_target(extdir, tmp_pathplus)

	def check_file(self, filename, content) -> None:
		assert os.path.isfile(filename)
		with open(filename, "rb") as f:
			assert f.read() == content

	def test_sanitize_windows_name(self):
		san = ZipFile._sanitize_windows_name
		# Passing pathsep in allows this test to work regardless of platform.
		assert san(r',,?,C:,foo,bar/z', ',') == r'_,C_,foo,bar/z'
		assert san(r'a\b,c<d>e|f"g?h*i', ',') == r'a\b,c_d_e_f_g_h_i'
		assert san("../../foo../../ba..r", '/') == r'foo/ba..r'

	def test_extract_hackers_arcnames_common_cases(self, tmp_pathplus: PathPlus):
		common_hacknames = [
				("../foo/bar", "foo/bar"),
				("foo/../bar", "foo/bar"),
				("foo/../../bar", "foo/bar"),
				("foo/bar/..", "foo/bar"),
				("./../foo/bar", "foo/bar"),
				("/foo/bar", "foo/bar"),
				("/foo/../bar", "foo/bar"),
				("/foo/../../bar", "foo/bar"),
				]
		self._test_extract_hackers_arcnames(common_hacknames, tmp_pathplus)

	@unittest.skipIf(os.path.sep != '\\', "Requires \\ as path separator.")
	def test_extract_hackers_arcnames_windows_only(self, tmp_pathplus: PathPlus):
		"""Test combination of path fixing and windows name sanitization."""
		windows_hacknames = [
				(r'..\foo\bar', "foo/bar"),
				(r'..\/foo\/bar', "foo/bar"),
				(r'foo/\..\/bar', "foo/bar"),
				(r'foo\/../\bar', "foo/bar"),
				(r'C:foo/bar', "foo/bar"),
				(r'C:/foo/bar', "foo/bar"),
				(r'C://foo/bar', "foo/bar"),
				(r'C:\foo\bar', "foo/bar"),
				(r'//conky/mountpoint/foo/bar', "foo/bar"),
				(r'\\conky\mountpoint\foo\bar', "foo/bar"),
				(r'///conky/mountpoint/foo/bar', "conky/mountpoint/foo/bar"),
				(r'\\\conky\mountpoint\foo\bar', "conky/mountpoint/foo/bar"),
				(r'//conky//mountpoint/foo/bar', "conky/mountpoint/foo/bar"),
				(r'\\conky\\mountpoint\foo\bar', "conky/mountpoint/foo/bar"),
				(r'//?/C:/foo/bar', "foo/bar"),
				(r'\\?\C:\foo\bar', "foo/bar"),
				(r'C:/../C:/foo/bar', "C_/foo/bar"),
				(r'a:b\c<d>e|f"g?h*i', "b/c_d_e_f_g_h_i"),
				("../../foo../../ba..r", "foo/ba..r"),
				]
		self._test_extract_hackers_arcnames(windows_hacknames, tmp_pathplus)

	@unittest.skipIf(os.path.sep != '/', r'Requires / as path separator.')
	def test_extract_hackers_arcnames_posix_only(self, tmp_pathplus: PathPlus):
		posix_hacknames = [
				("//foo/bar", "foo/bar"),
				("../../foo../../ba..r", "foo../ba..r"),
				(r'foo/..\bar', r'foo/..\bar'),
				]
		self._test_extract_hackers_arcnames(posix_hacknames, tmp_pathplus)

	def _test_extract_hackers_arcnames(self, hacknames, tmp_pathplus):
		for arcname, fixedname in hacknames:
			content = b'foobar' + arcname.encode()
			with ZipFile(tmp_pathplus / TESTFN2, 'w', zipfile.ZIP_STORED) as zipfp:
				zinfo = zipfile.ZipInfo()
				# preserve backslashes
				zinfo.filename = arcname
				zinfo.external_attr = 0o600 << 16
				zipfp.writestr(zinfo, content)

			arcname = arcname.replace(os.sep, '/')
			targetpath = os.path.join("target", "subdir", "subsub")
			correctfile = os.path.join(targetpath, *fixedname.split('/'))

			with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
				writtenfile = zipfp.extract(arcname, targetpath)
				assert writtenfile == correctfile, f"extract {arcname!r}: {writtenfile!r} != {correctfile!r}"
			self.check_file(correctfile, content)
			rmtree("target")

			with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
				zipfp.extractall(targetpath)
			self.check_file(correctfile, content)
			rmtree("target")

			correctfile = os.path.join(os.getcwd(), *fixedname.split('/'))

			with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
				writtenfile = zipfp.extract(arcname)
				assert writtenfile == correctfile, f"extract {arcname!r}"
			self.check_file(correctfile, content)
			rmtree(fixedname.split('/')[0])

			with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
				zipfp.extractall()
			self.check_file(correctfile, content)
			rmtree(fixedname.split('/')[0])


class TestsOther:

	def test_open_via_zip_info(self, tmp_pathplus: PathPlus):
		# Create the ZIP archive
		with ZipFile(tmp_pathplus / TESTFN2, 'w', zipfile.ZIP_STORED) as zipfp:
			zipfp.writestr("name", "foo")
			with pytest.warns(UserWarning):
				zipfp.writestr("name", "bar")
			assert zipfp.namelist() == ["name"] * 2

		with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
			infos = zipfp.infolist()
			data = b""
			for info in infos:
				with zipfp.open(info) as zipopen:
					data += zipopen.read()
			assert data in {b"foobar", b"barfoo"}
			data = b""
			for info in infos:
				data += zipfp.read(info)
			assert data in {b"foobar", b"barfoo"}

	def test_writestr_extended_local_header_issue1202(self, tmp_pathplus: PathPlus):
		with ZipFile(tmp_pathplus / TESTFN2, 'w') as orig_zip:
			for data in "abcdefghijklmnop":
				zinfo = zipfile.ZipInfo(data)
				zinfo.flag_bits |= 0x08  # Include an extended local header.
				orig_zip.writestr(zinfo, data)

	def test_close(self, tmp_pathplus: PathPlus):
		"""Check that the zipfile is closed after the 'with' block."""
		with ZipFile(tmp_pathplus / TESTFN2, 'w') as zipfp:
			for fpath, fdata in SMALL_TEST_DATA:
				zipfp.writestr(fpath, fdata)
				assert zipfp.fp is not None, "zipfp is not open"
		assert zipfp.fp is None, "zipfp is not closed"

		with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
			assert zipfp.fp is not None, "zipfp is not open"
		assert zipfp.fp is None, "zipfp is not closed"

	def test_close_on_exception(self, tmp_pathplus: PathPlus):
		"""Check that the zipfile is closed if an exception is raised in the
		'with' block."""
		with ZipFile(tmp_pathplus / TESTFN2, 'w') as zipfp:
			for fpath, fdata in SMALL_TEST_DATA:
				zipfp.writestr(fpath, fdata)

		# pylint: disable=used-before-assignment
		try:
			with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp2:
				raise zipfile.BadZipFile()
		except zipfile.BadZipFile:
			assert zipfp2.fp is None, "zipfp is not closed"
		# pylint: enable=used-before-assignment

	def test_unsupported_version(self):
		# File has an extract_version of 120
		data = (
				b'PK\x03\x04x\x00\x00\x00\x00\x00!p\xa1@\x00\x00\x00\x00\x00\x00'
				b'\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00xPK\x01\x02x\x03x\x00\x00\x00\x00'
				b'\x00!p\xa1@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00'
				b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x01\x00\x00\x00\x00xPK\x05\x06'
				b'\x00\x00\x00\x00\x01\x00\x01\x00/\x00\x00\x00\x1f\x00\x00\x00\x00\x00'
				)

		with pytest.raises(NotImplementedError):
			ZipFile(io.BytesIO(data), 'r')

	@requires_zlib()
	def test_read_unicode_filenames(self):
		# bug #10801
		fname = findfile("zip_cp437_header.zip")
		with ZipFile(fname) as zipfp:
			for name in zipfp.namelist():
				zipfp.open(name).close()

	def test_write_unicode_filenames(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		with ZipFile(testfn, 'w') as zf:
			zf.writestr("foo.txt", "Test for unicode filename")
			zf.writestr("ö.txt", "Test for unicode filename")
			assert isinstance(zf.infolist()[0].filename, str)

		with ZipFile(testfn, 'r') as zf:
			assert zf.filelist[0].filename == "foo.txt"
			assert zf.filelist[1].filename == "ö.txt"

	@min_version(3.8)
	def test_read_after_write_unicode_filenames(self, tmp_pathplus: PathPlus):
		with ZipFile(tmp_pathplus / TESTFN2, 'w') as zipfp:
			zipfp.writestr("приклад", b'sample')
			assert zipfp.read("приклад") == b'sample'

	def test_exclusive_create_zip_file(self, tmp_pathplus: PathPlus):
		"""Test exclusive creating a new zipfile."""
		unlink(tmp_pathplus / TESTFN2)
		filename = "testfile.txt"
		content = b'hello, world. this is some content.'
		with ZipFile(tmp_pathplus / TESTFN2, 'x', zipfile.ZIP_STORED) as zipfp:
			zipfp.writestr(filename, content)
		with pytest.raises(FileExistsError):
			ZipFile(tmp_pathplus / TESTFN2, 'x', zipfile.ZIP_STORED)
		with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipfp:
			assert zipfp.namelist() == [filename]
			assert zipfp.read(filename) == content

	def test_create_non_existent_file_for_append(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		filename = "testfile.txt"
		content = b'hello, world. this is some content.'

		try:
			with ZipFile(testfn, 'a') as zf:
				zf.writestr(filename, content)
		except OSError:
			pytest.fail("Could not append data to a non-existent zip file.")

		assert os.path.exists(tmp_pathplus / TESTFN)

		with ZipFile(testfn, 'r') as zf:
			assert zf.read(filename) == content

	def test_close_erroneous_file(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# This test checks that the ZipFile constructor closes the file object
		# it opens if there's an error in the file.  If it doesn't, the
		# traceback holds a reference to the ZipFile object and, indirectly,
		# the file object.
		# On Windows, this causes the os.unlink() call to fail because the
		# underlying file is still open.  This is SF bug #412214.
		#
		with open(testfn, 'w', encoding="utf-8") as fp:
			fp.write("this is not a legal zip file\n")
		try:
			ZipFile(tmp_pathplus / TESTFN)
		except zipfile.BadZipFile:
			pass

	def test_is_zip_erroneous_file(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		"""Check that is_zipfile() correctly identifies non-zip files."""

		with open(testfn, 'w', encoding="utf-8") as fp:
			fp.write("this is not a legal zip file\n")

		# - passing a filename
		assert not zipfile.is_zipfile(str(tmp_pathplus / TESTFN))
		# - passing a path-like object
		assert not zipfile.is_zipfile(tmp_pathplus / TESTFN)
		# - passing a file object
		with open(testfn, "rb") as fp:
			assert not zipfile.is_zipfile(fp)

		# - passing a file-like object
		fp = io.BytesIO()
		fp.write(b"this is not a legal zip file\n")
		assert not zipfile.is_zipfile(fp)
		fp.seek(0, 0)
		assert not zipfile.is_zipfile(fp)

	def test_damaged_zipfile(self):
		"""Check that zipfiles with missing bytes at the end raise BadZipFile."""
		# - Create a valid zip file
		fp = io.BytesIO()
		with ZipFile(fp, mode='w') as zipf:
			zipf.writestr("foo.txt", b"O, for a Muse of Fire!")
		zipfiledata = fp.getvalue()

		# - Now create copies of it missing the last N bytes and make sure
		#   a BadZipFile exception is raised when we try to open it
		for N in range(len(zipfiledata)):
			fp = io.BytesIO(zipfiledata[:N])
			with pytest.raises(zipfile.BadZipFile):
				ZipFile(fp)

	def test_is_zip_valid_file(self, tmp_pathplus, testfn: PathPlus):
		"""Check that is_zipfile() correctly identifies zip files."""
		# - passing a filename
		with ZipFile(testfn, mode='w') as zipf:
			zipf.writestr("foo.txt", b"O, for a Muse of Fire!")

		assert zipfile.is_zipfile(tmp_pathplus / TESTFN)
		# - passing a file object
		with open(testfn, "rb") as fp:
			assert zipfile.is_zipfile(fp)
			fp.seek(0, 0)
			zip_contents = fp.read()
		# - passing a file-like object
		fp = io.BytesIO()
		fp.write(zip_contents)
		assert zipfile.is_zipfile(fp)
		fp.seek(0, 0)
		assert zipfile.is_zipfile(fp)

	def test_non_existent_file_raises_OSError(self, tmp_pathplus: PathPlus):
		# make sure we don't raise an AttributeError when a partially-constructed
		# ZipFile instance is finalized; this tests for regression on SF tracker
		# bug #403871.

		# The bug we're testing for caused an AttributeError to be raised
		# when a ZipFile instance was created for a file that did not
		# exist; the .fp member was not initialized but was needed by the
		# __del__() method.  Since the AttributeError is in the __del__(),
		# it is ignored, but the user should be sufficiently annoyed by
		# the message on the output that regression will be noticed uickly.

		with pytest.raises(OSError, match=r"\[Errno 2\] No such file or directory: "):
			ZipFile(tmp_pathplus / TESTFN)

	def test_empty_file_raises_BadZipFile(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		f = open(testfn, 'w', encoding="utf-8")
		f.close()
		with pytest.raises(zipfile.BadZipFile):
			ZipFile(tmp_pathplus / TESTFN)

		with open(testfn, 'w', encoding="utf-8") as fp:
			fp.write("short file")
		with pytest.raises(zipfile.BadZipFile):
			ZipFile(tmp_pathplus / TESTFN)

	def test_closed_zip_raises_ValueError(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		"""Verify that testzip() doesn't swallow inappropriate exceptions."""
		data = io.BytesIO()
		with ZipFile(data, mode='w') as zipf:
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")

		# This is correct; calling .read on a closed ZipFile should raise
		# a ValueError, and so should calling .testzip.  An earlier
		# version of .testzip would swallow this exception (and any other)
		# and report that the first file in the archive was corrupt.
		with pytest.raises(ValueError, match="Attempt to use ZIP archive that was already closed"):
			zipf.read("foo.txt")
		with pytest.raises(ValueError, match="Attempt to use ZIP archive that was already closed"):
			zipf.open("foo.txt")
		with pytest.raises(ValueError, match="Attempt to use ZIP archive that was already closed"):
			zipf.testzip()
		with pytest.raises(ValueError, match="Attempt to write to ZIP archive that was already closed"):
			zipf.writestr("bogus.txt", "bogus")
		with open(testfn, 'w', encoding="utf-8") as f:
			f.write("zipfile test data")
		with pytest.raises(ValueError, match="Attempt to write to ZIP archive that was already closed"):
			zipf.write(tmp_pathplus / TESTFN)

	def test_bad_constructor_mode(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Check that bad modes passed to ZipFile constructor are caught.
		with pytest.raises(ValueError, match="ZipFile requires mode 'r', 'w', 'x', or 'a'"):
			ZipFile(testfn, 'q')

	def test_bad_open_mode(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Check that bad modes passed to ZipFile.open are caught.
		with ZipFile(testfn, mode='w') as zipf:
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")

		with ZipFile(testfn, mode='r') as zipf:
			# read the data to make sure the file is there
			zipf.read("foo.txt")
			with pytest.raises(ValueError, match=r'open\(\) requires mode "r" or "w"'):
				zipf.open("foo.txt", 'q')
			# universal newlines support is removed
			with pytest.raises(ValueError, match=r'open\(\) requires mode "r" or "w"'):
				zipf.open("foo.txt", 'U')
			with pytest.raises(ValueError, match=r'open\(\) requires mode "r" or "w"'):
				zipf.open("foo.txt", "rU")

	def test_read0(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Check that calling read(0) on a ZipExtFile object returns an empty string
		# and doesn't advance file pointer.

		with ZipFile(testfn, mode='w') as zipf:
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")
			# read the data to make sure the file is there
			with zipf.open("foo.txt") as f:
				for i in range(FIXEDTEST_SIZE):
					assert f.read(0) == b''

				assert f.read() == b"O, for a Muse of Fire!"

	def test_open_non_existent_item(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		"""Check that attempting to call open() for an item that doesn't
		exist in the archive raises a RuntimeError."""
		with ZipFile(testfn, mode='w') as zipf:
			with pytest.raises(KeyError):
				zipf.open("foo.txt", 'r')

	def test_bad_compression_mode(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		"""Check that bad compression methods passed to ZipFile.open are
		caught."""
		with pytest.raises(NotImplementedError):
			ZipFile(testfn, 'w', -1)

	def test_unsupported_compression(self):
		# data is declared as shrunk, but actually deflated
		data = (
				b'PK\x03\x04.\x00\x00\x00\x01\x00\xe4C\xa1@\x00\x00\x00'
				b'\x00\x02\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00x\x03\x00PK\x01'
				b'\x02.\x03.\x00\x00\x00\x01\x00\xe4C\xa1@\x00\x00\x00\x00\x02\x00\x00'
				b'\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
				b'\x80\x01\x00\x00\x00\x00xPK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x00'
				b'/\x00\x00\x00!\x00\x00\x00\x00\x00'
				)
		with ZipFile(io.BytesIO(data), 'r') as zipf:
			with pytest.raises(NotImplementedError):
				zipf.open('x')

	def test_null_byte_in_filename(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		"""Check that a filename containing a null byte is properly
		terminated."""
		with ZipFile(testfn, mode='w') as zipf:
			zipf.writestr("foo.txt\u0000qqq", b"O, for a Muse of Fire!")
			assert zipf.namelist() == ["foo.txt"]

	def test_comments(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		"""Check that comments on the archive are handled properly."""

		# check default comment is empty
		with ZipFile(testfn, mode='w') as zipf:
			assert zipf.comment == b''
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")

		with ZipFile(testfn, mode='r') as zipfr:
			assert zipfr.comment == b''

		# check a simple short comment
		comment = b'Bravely taking to his feet, he beat a very brave retreat.'
		with ZipFile(testfn, mode='w') as zipf:
			zipf.comment = comment
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")
		with ZipFile(testfn, mode='r') as zipfr:
			assert zipf.comment == comment

		# check a comment of max length
		comment2 = ''.join([f"{i ** 3 % 10:d}" for i in range((1 << 16) - 1)])
		comment2 = comment2.encode("ascii")
		with ZipFile(testfn, mode='w') as zipf:
			zipf.comment = comment2
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")

		with ZipFile(testfn, mode='r') as zipfr:
			assert zipfr.comment == comment2

		# check a comment that is too long is truncated
		with ZipFile(testfn, mode='w') as zipf:
			with pytest.warns(UserWarning):
				zipf.comment = comment2 + b'oops'
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")
		with ZipFile(testfn, mode='r') as zipfr:
			assert zipfr.comment == comment2

		# check that comments are correctly modified in append mode
		with ZipFile(testfn, mode='w') as zipf:
			zipf.comment = b"original comment"
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")
		with ZipFile(testfn, mode='a') as zipf:
			zipf.comment = b"an updated comment"
		with ZipFile(testfn, mode='r') as zipf:
			assert zipf.comment == b"an updated comment"

	def test_unicode_comment(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		with ZipFile(testfn, 'w', zipfile.ZIP_STORED) as zipf:
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")
			with pytest.raises(TypeError):
				zipf.comment = "this is an error"

	def test_change_comment_in_empty_archive(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		with ZipFile(testfn, 'a', zipfile.ZIP_STORED) as zipf:
			assert not zipf.filelist
			zipf.comment = b"this is a comment"
		with ZipFile(testfn, 'r') as zipf:
			assert zipf.comment == b"this is a comment"

	def test_change_comment_in_nonempty_archive(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		with ZipFile(testfn, 'w', zipfile.ZIP_STORED) as zipf:
			zipf.writestr("foo.txt", "O, for a Muse of Fire!")
		with ZipFile(testfn, 'a', zipfile.ZIP_STORED) as zipf:
			assert zipf.filelist
			zipf.comment = b"this is a comment"
		with ZipFile(testfn, 'r') as zipf:
			assert zipf.comment == b"this is a comment"

	def test_empty_zipfile(self, testfn: PathPlus):
		# Check that creating a file in 'w' or 'a' mode and closing without
		# adding any files to the archives creates a valid empty ZIP file

		zipf = ZipFile(testfn, mode='w')
		zipf.close()
		try:
			ZipFile(testfn, mode='r')
		except zipfile.BadZipFile:
			pytest.fail("Unable to create empty ZIP file in 'w' mode")

		zipf = ZipFile(testfn, mode='a')
		zipf.close()
		try:
			ZipFile(testfn, mode='r')
		except Exception:
			pytest.fail("Unable to create empty ZIP file in 'a' mode")

	def test_open_empty_file(self, testfn: PathPlus):
		# Issue 1710703: Check that opening a file with less than 22 bytes
		# raises a BadZipFile exception (rather than the previously unhelpful OSError)

		with open(testfn, 'w', encoding="utf-8") as f:
			pass

		with pytest.raises(zipfile.BadZipFile):
			ZipFile(testfn, 'r')

	def test_zipfile_with_short_extra_field(self):
		"""If an extra field in the header is less than 4 bytes, skip it."""
		zipdata = (
				b'PK\x03\x04\x14\x00\x00\x00\x00\x00\x93\x9b\xad@\x8b\x9e'
				b'\xd9\xd3\x01\x00\x00\x00\x01\x00\x00\x00\x03\x00\x03\x00ab'
				b'c\x00\x00\x00APK\x01\x02\x14\x03\x14\x00\x00\x00\x00'
				b'\x00\x93\x9b\xad@\x8b\x9e\xd9\xd3\x01\x00\x00\x00\x01\x00\x00'
				b'\x00\x03\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa4\x81\x00'
				b'\x00\x00\x00abc\x00\x00PK\x05\x06\x00\x00\x00\x00'
				b'\x01\x00\x01\x003\x00\x00\x00%\x00\x00\x00\x00\x00'
				)
		with ZipFile(io.BytesIO(zipdata), 'r') as zipf:
			# testzip returns the name of the first corrupt file, or None
			assert zipf.testzip() is None

	def test_open_conflicting_handles(self, tmp_pathplus: PathPlus):
		# It's only possible to open one writable file handle at a time
		msg1 = b"It's fun to charter an accountant!"
		msg2 = b"And sail the wide accountant sea"
		msg3 = b"To find, explore the funds offshore"
		with ZipFile(tmp_pathplus / TESTFN2, 'w', zipfile.ZIP_STORED) as zipf:
			with zipf.open("foo", mode='w') as w2:
				w2.write(msg1)
			with zipf.open("bar", mode='w') as w1:

				cant_write_msg = (
						"Can't write to the ZIP file while there is another write handle open on it. "
						"Close the first handle before opening another."
						)
				with pytest.raises(ValueError, match=cant_write_msg):
					zipf.open("handle", mode='w')

				cant_read_msg = (
						"Can't read from the ZIP file while there is an open writing handle on it. "
						"Close the writing handle before trying to read."
						)
				with pytest.raises(ValueError, match=cant_read_msg):
					zipf.open("foo", mode='r')

				with pytest.raises(
						ValueError,
						match="Can't write to ZIP archive while an open writing handle exists",
						):
					zipf.writestr("str", "abcde")

				with pytest.raises(
						ValueError,
						match="Can't write to ZIP archive while an open writing handle exists",
						):
					zipf.write(__file__, "file")

				cant_close_msg = (
						"Can't close the ZIP file while there is an open writing handle on it. "
						"Close the writing handle before closing the zip."
						)
				with pytest.raises(ValueError, match=cant_close_msg):
					zipf.close()

				w1.write(msg2)
			with zipf.open("baz", mode='w') as w2:
				w2.write(msg3)

		with ZipFile(tmp_pathplus / TESTFN2, 'r') as zipf:
			assert zipf.read("foo") == msg1
			assert zipf.read("bar") == msg2
			assert zipf.read("baz") == msg3
			assert zipf.namelist() == ["foo", "bar", "baz"]

	@min_version(3.7)
	def test_seek_tell(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Test seek functionality
		txt = b"Where's Bruce?"
		bloc = txt.find(b"Bruce")
		# Check seek on a file
		with ZipFile(testfn, 'w') as zipf:
			zipf.writestr("foo.txt", txt)
		with ZipFile(testfn, 'r') as zipf:
			with zipf.open("foo.txt", 'r') as fp:
				fp.seek(bloc, os.SEEK_SET)
				assert fp.tell() == bloc
				fp.seek(-bloc, os.SEEK_CUR)
				assert fp.tell() == 0
				fp.seek(bloc, os.SEEK_CUR)
				assert fp.tell() == bloc
				assert fp.read(5) == txt[bloc:bloc + 5]
				fp.seek(0, os.SEEK_END)
				assert fp.tell() == len(txt)
				fp.seek(0, os.SEEK_SET)
				assert fp.tell() == 0
		# Check seek on memory file
		data = io.BytesIO()
		with ZipFile(data, mode='w') as zipf:
			zipf.writestr("foo.txt", txt)
		with ZipFile(data, mode='r') as zipf:
			with zipf.open("foo.txt", 'r') as fp:
				fp.seek(bloc, os.SEEK_SET)
				assert fp.tell() == bloc
				fp.seek(-bloc, os.SEEK_CUR)
				assert fp.tell() == 0
				fp.seek(bloc, os.SEEK_CUR)
				assert fp.tell() == bloc
				assert fp.read(5) == txt[bloc:bloc + 5]
				fp.seek(0, os.SEEK_END)
				assert fp.tell() == len(txt)
				fp.seek(0, os.SEEK_SET)
				assert fp.tell() == 0

	@requires_bz2()
	def test_decompress_without_3rd_party_library(self):
		data = b'PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		zip_file = io.BytesIO(data)
		with ZipFile(zip_file, 'w', compression=zipfile.ZIP_BZIP2) as zf:
			zf.writestr("a.txt", b'a')
		with mock.patch("zipfile.bz2", None):
			with ZipFile(zip_file) as zf:

				if sys.version_info < (3, 8):
					with pytest.raises(AttributeError):
						zf.extract("a.txt")
				else:
					with pytest.raises(RuntimeError):
						zf.extract("a.txt")


class AbstractBadCrcTests:
	zip_with_bad_crc: bytes

	def test_testzip_with_bad_crc(self):
		"""Tests that files with bad CRCs return their name from testzip."""
		zipdata = self.zip_with_bad_crc

		with ZipFile(io.BytesIO(zipdata), mode='r') as zipf:
			# testzip returns the name of the first corrupt file, or None
			assert "afile" == zipf.testzip()

	def test_read_with_bad_crc(self):
		"""Tests that files with bad CRCs raise a BadZipFile exception when read."""
		zipdata = self.zip_with_bad_crc

		# Using ZipFile.read()
		with ZipFile(io.BytesIO(zipdata), mode='r') as zipf:
			with pytest.raises(zipfile.BadZipFile):
				zipf.read("afile")

		# Using ZipExtFile.read()
		with ZipFile(io.BytesIO(zipdata), mode='r') as zipf:
			with zipf.open("afile", 'r') as corrupt_file:
				with pytest.raises(zipfile.BadZipFile):
					corrupt_file.read()

		# Same with small reads (in order to exercise the buffering logic)
		with ZipFile(io.BytesIO(zipdata), mode='r') as zipf:
			with zipf.open("afile", 'r') as corrupt_file:
				corrupt_file.MIN_READ_SIZE = 2
				with pytest.raises(zipfile.BadZipFile):  # noqa: PT012
					while corrupt_file.read(2):
						pass


class TestStoredBadCrc(AbstractBadCrcTests):
	compression = zipfile.ZIP_STORED
	zip_with_bad_crc = (
			b'PK\003\004\024\0\0\0\0\0 \213\212;:r'
			b'\253\377\f\0\0\0\f\0\0\0\005\0\0\000af'
			b'ilehello,AworldP'
			b'K\001\002\024\003\024\0\0\0\0\0 \213\212;:'
			b'r\253\377\f\0\0\0\f\0\0\0\005\0\0\0\0'
			b'\0\0\0\0\0\0\0\200\001\0\0\0\000afi'
			b'lePK\005\006\0\0\0\0\001\0\001\0003\000'
			b'\0\0/\0\0\0\0\0'
			)


@requires_zlib()
class TestDeflateBadCrcTests(AbstractBadCrcTests):
	compression = zipfile.ZIP_DEFLATED
	zip_with_bad_crc = (
			b'PK\x03\x04\x14\x00\x00\x00\x08\x00n}\x0c=FA'
			b'KE\x10\x00\x00\x00n\x00\x00\x00\x05\x00\x00\x00af'
			b'ile\xcbH\xcd\xc9\xc9W(\xcf/\xcaI\xc9\xa0'
			b'=\x13\x00PK\x01\x02\x14\x03\x14\x00\x00\x00\x08\x00n'
			b'}\x0c=FAKE\x10\x00\x00\x00n\x00\x00\x00\x05'
			b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x01\x00\x00\x00'
			b'\x00afilePK\x05\x06\x00\x00\x00\x00\x01\x00'
			b'\x01\x003\x00\x00\x003\x00\x00\x00\x00\x00'
			)


@requires_bz2()
class TestBzip2BadCrc(AbstractBadCrcTests):
	compression = zipfile.ZIP_BZIP2
	zip_with_bad_crc = (
			b'PK\x03\x04\x14\x03\x00\x00\x0c\x00nu\x0c=FA'
			b'KE8\x00\x00\x00n\x00\x00\x00\x05\x00\x00\x00af'
			b'ileBZh91AY&SY\xd4\xa8\xca'
			b'\x7f\x00\x00\x0f\x11\x80@\x00\x06D\x90\x80 \x00 \xa5'
			b'P\xd9!\x03\x03\x13\x13\x13\x89\xa9\xa9\xc2u5:\x9f'
			b'\x8b\xb9"\x9c(HjTe?\x80PK\x01\x02\x14'
			b'\x03\x14\x03\x00\x00\x0c\x00nu\x0c=FAKE8'
			b'\x00\x00\x00n\x00\x00\x00\x05\x00\x00\x00\x00\x00\x00\x00\x00'
			b'\x00 \x80\x80\x81\x00\x00\x00\x00afilePK'
			b'\x05\x06\x00\x00\x00\x00\x01\x00\x01\x003\x00\x00\x00[\x00'
			b'\x00\x00\x00\x00'
			)


@requires_lzma()
class TestLzmaBadCrc(AbstractBadCrcTests):
	compression = zipfile.ZIP_LZMA
	zip_with_bad_crc = (
			b'PK\x03\x04\x14\x03\x00\x00\x0e\x00nu\x0c=FA'
			b'KE\x1b\x00\x00\x00n\x00\x00\x00\x05\x00\x00\x00af'
			b'ile\t\x04\x05\x00]\x00\x00\x00\x04\x004\x19I'
			b'\xee\x8d\xe9\x17\x89:3`\tq!.8\x00PK'
			b'\x01\x02\x14\x03\x14\x03\x00\x00\x0e\x00nu\x0c=FA'
			b'KE\x1b\x00\x00\x00n\x00\x00\x00\x05\x00\x00\x00\x00\x00'
			b'\x00\x00\x00\x00 \x80\x80\x81\x00\x00\x00\x00afil'
			b'ePK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x003\x00\x00'
			b'\x00>\x00\x00\x00\x00\x00'
			)


@pytest.fixture()
def encrypted_zip(testfn: PathPlus) -> Iterator[ZipFile]:

	data = (
			b'PK\x03\x04\x14\x00\x01\x00\x00\x00n\x92i.#y\xef?&\x00\x00\x00\x1a\x00'
			b'\x00\x00\x08\x00\x00\x00test.txt\xfa\x10\xa0gly|\xfa-\xc5\xc0=\xf9y'
			b'\x18\xe0\xa8r\xb3Z}Lg\xbc\xae\xf9|\x9b\x19\xe4\x8b\xba\xbb)\x8c\xb0\xdbl'
			b'PK\x01\x02\x14\x00\x14\x00\x01\x00\x00\x00n\x92i.#y\xef?&\x00\x00\x00'
			b'\x1a\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x01\x00 \x00\xb6\x81'
			b'\x00\x00\x00\x00test.txtPK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x006\x00'
			b'\x00\x00L\x00\x00\x00\x00\x00'
			)

	with open(testfn, "wb") as fp:
		fp.write(data)

	with ZipFile(testfn, 'r') as zip1:
		yield zip1


@pytest.fixture()
def encrypted_zip2(tmp_pathplus: PathPlus, testfn: PathPlus) -> Iterator[ZipFile]:
	data2 = (
			b'PK\x03\x04\x14\x00\t\x00\x08\x00\xcf}38xu\xaa\xb2\x14\x00\x00\x00\x00\x02'
			b'\x00\x00\x04\x00\x15\x00zeroUT\t\x00\x03\xd6\x8b\x92G\xda\x8b\x92GUx\x04'
			b'\x00\xe8\x03\xe8\x03\xc7<M\xb5a\xceX\xa3Y&\x8b{oE\xd7\x9d\x8c\x98\x02\xc0'
			b'PK\x07\x08xu\xaa\xb2\x14\x00\x00\x00\x00\x02\x00\x00PK\x01\x02\x17\x03'
			b'\x14\x00\t\x00\x08\x00\xcf}38xu\xaa\xb2\x14\x00\x00\x00\x00\x02\x00\x00'
			b'\x04\x00\r\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa4\x81\x00\x00\x00\x00ze'
			b'roUT\x05\x00\x03\xd6\x8b\x92GUx\x00\x00PK\x05\x06\x00\x00\x00\x00\x01'
			b'\x00\x01\x00?\x00\x00\x00[\x00\x00\x00\x00\x00'
			)

	with open(tmp_pathplus / TESTFN2, "wb") as fp:
		fp.write(data2)

	with ZipFile(tmp_pathplus / TESTFN2, 'r') as zip2:
		yield zip2


class TestDecryption:
	"""Check that ZIP decryption works. Since the library does not
	support encryption at the moment, we use a pre-generated encrypted
	ZIP file."""

	plain = b'zipfile.py encryption test'
	plain2 = b'\x00' * 512

	def test_no_password(self, encrypted_zip: ZipFile, encrypted_zip2: ZipFile):
		# Reading the encrypted file without password
		# must generate a RunTime exception
		with pytest.raises(RuntimeError):
			encrypted_zip.read("test.txt")
		with pytest.raises(RuntimeError):
			encrypted_zip2.read("zero")

	def test_bad_password(self, encrypted_zip: ZipFile, encrypted_zip2: ZipFile):
		encrypted_zip.setpassword(b"perl")
		with pytest.raises(RuntimeError):
			encrypted_zip.read("test.txt")
		encrypted_zip2.setpassword(b"perl")
		with pytest.raises(RuntimeError):
			encrypted_zip2.read("zero")

	@requires_zlib()
	def test_good_password(self, encrypted_zip: ZipFile, encrypted_zip2: ZipFile):
		encrypted_zip.setpassword(b"python")
		assert encrypted_zip.read("test.txt") == self.plain
		encrypted_zip2.setpassword(b"12345")
		assert encrypted_zip2.read("zero") == self.plain2

	@no_type_check
	def test_unicode_password(self, encrypted_zip: ZipFile, encrypted_zip2: ZipFile):
		with pytest.raises(TypeError):
			encrypted_zip.setpassword("unicode")
		with pytest.raises(TypeError):
			encrypted_zip.read("test.txt", "python")
		with pytest.raises(TypeError):
			encrypted_zip.open("test.txt", pwd="python")
		with pytest.raises(TypeError):
			encrypted_zip.extract("test.txt", pwd="python")

	@min_version(3.7)
	def test_seek_tell(self, encrypted_zip: ZipFile, encrypted_zip2: ZipFile):
		encrypted_zip.setpassword(b"python")
		txt = self.plain
		test_word = b'encryption'
		bloc = txt.find(test_word)
		bloc_len = len(test_word)
		with encrypted_zip.open("test.txt", 'r') as fp:
			fp.seek(bloc, os.SEEK_SET)
			assert fp.tell() == bloc
			fp.seek(-bloc, os.SEEK_CUR)
			assert fp.tell() == 0
			fp.seek(bloc, os.SEEK_CUR)
			assert fp.tell() == bloc
			assert fp.read(bloc_len) == txt[bloc:bloc + bloc_len]

			# Make sure that the second read after seeking back beyond
			# _readbuffer returns the same content (ie. rewind to the start of
			# the file to read forward to the required position).
			old_read_size = fp.MIN_READ_SIZE
			fp.MIN_READ_SIZE = 1
			fp._readbuffer = b''
			fp._offset = 0
			fp.seek(0, os.SEEK_SET)
			assert fp.tell() == 0
			fp.seek(bloc, os.SEEK_CUR)
			assert fp.read(bloc_len) == txt[bloc:bloc + bloc_len]
			fp.MIN_READ_SIZE = old_read_size

			fp.seek(0, os.SEEK_END)
			assert fp.tell() == len(txt)
			fp.seek(0, os.SEEK_SET)
			assert fp.tell() == 0

			# Read the file completely to definitely call any eof integrity
			# checks (crc) and make sure they still pass.
			fp.read()


class AbstractTestsWithRandomBinaryFiles:

	@classmethod
	def setup_class(cls) -> None:
		datacount = random.randint(16, 64) * 1024 + random.randint(1, 1024)
		cls.data = b''.join(
				struct.pack("<f", random.random() * random.randint(-1000, 1000)) for i in range(datacount)
				)

	def make_test_archive(self, f, tmpdir, compression) -> None:
		# Create the ZIP archive
		with ZipFile(f, 'w', compression) as zipfp:
			zipfp.write(tmpdir / TESTFN, "another.name")
			zipfp.write(tmpdir / TESTFN, TESTFN)

	def zip_test(self, f, tmpdir: PathPlus, compression: int):
		self.make_test_archive(f, tmpdir, compression)

		# Read the ZIP archive
		with ZipFile(f, 'r', compression) as zipfp:
			testdata = zipfp.read(TESTFN)
			assert len(testdata) == len(self.data)
			assert testdata == self.data
			assert zipfp.read("another.name") == self.data

	def test_read(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.zip_test(f, tmp_pathplus, self.compression)

	def zip_open_test(self, f, tmpdir, compression):
		self.make_test_archive(f, tmpdir, compression)

		# Read the ZIP archive
		with ZipFile(f, 'r', compression) as zipfp:
			zipdata1 = []
			with zipfp.open(TESTFN) as zipopen1:
				while True:
					read_data = zipopen1.read(256)
					if not read_data:
						break
					zipdata1.append(read_data)

			zipdata2 = []
			with zipfp.open("another.name") as zipopen2:
				while True:
					read_data = zipopen2.read(256)
					if not read_data:
						break
					zipdata2.append(read_data)

			testdata1 = b''.join(zipdata1)
			assert len(testdata1) == len(self.data)
			assert testdata1 == self.data

			testdata2 = b''.join(zipdata2)
			assert len(testdata2) == len(self.data)
			assert testdata2 == self.data

	def test_open(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.zip_open_test(f, tmp_pathplus, self.compression)

	def test_random_open(self, tmp_pathplus: PathPlus, testfn: PathPlus):

		# Make a source file with some lines
		with open(testfn, "wb") as fp:
			fp.write(self.data)

		for f in get_files(tmp_pathplus):
			self.make_test_archive(f, tmp_pathplus, self.compression)

			# Read the ZIP archive
			with ZipFile(f, 'r', self.compression) as zipfp:
				zipdata1 = []
				with zipfp.open(TESTFN) as zipopen1:
					while True:
						read_data = zipopen1.read(random.randint(1, 1024))
						if not read_data:
							break
						zipdata1.append(read_data)

				testdata = b''.join(zipdata1)
				assert len(testdata) == len(self.data)
				assert testdata == self.data


class TestStoredTestsWithRandomBinaryFiles(AbstractTestsWithRandomBinaryFiles):
	compression = zipfile.ZIP_STORED


@requires_zlib()
class TesteflateTestsWithRandomBinaryFiles(AbstractTestsWithRandomBinaryFiles):
	compression = zipfile.ZIP_DEFLATED


@requires_bz2()
class TestBzip2TestsWithRandomBinaryFiles(AbstractTestsWithRandomBinaryFiles):
	compression = zipfile.ZIP_BZIP2


@requires_lzma()
class TestLzmaTestsWithRandomBinaryFiles(AbstractTestsWithRandomBinaryFiles):
	compression = zipfile.ZIP_LZMA


@min_version(3.9)
@requires_zlib()
class TestsWithMultipleOpens:

	@classmethod
	def setup_class(cls):
		cls.data1 = b'111' + random.randbytes(10000)
		cls.data2 = b'222' + random.randbytes(10000)

	def make_test_archive(self, f):
		# Create the ZIP archive
		with ZipFile(f, 'w', zipfile.ZIP_DEFLATED) as zipfp:
			zipfp.writestr("ones", self.data1)
			zipfp.writestr("twos", self.data2)

	def test_same_file(self, tmp_pathplus: PathPlus):
		# Verify that (when the ZipFile is in control of creating file objects)
		# multiple open() calls can be made without interfering with each other.
		for f in get_files(tmp_pathplus):
			self.make_test_archive(f)
			with ZipFile(f, mode='r') as zipf:
				with zipf.open("ones") as zopen1, zipf.open("ones") as zopen2:
					data1 = zopen1.read(500)
					data2 = zopen2.read(500)
					data1 += zopen1.read()
					data2 += zopen2.read()
				assert data1 == data2
				assert data1 == self.data1

	def test_different_file(self, tmp_pathplus: PathPlus):
		# Verify that (when the ZipFile is in control of creating file objects)
		# multiple open() calls can be made without interfering with each other.
		for f in get_files(tmp_pathplus):
			self.make_test_archive(f)
			with ZipFile(f, mode='r') as zipf:
				with zipf.open("ones") as zopen1, zipf.open("twos") as zopen2:
					data1 = zopen1.read(500)
					data2 = zopen2.read(500)
					data1 += zopen1.read()
					data2 += zopen2.read()
				assert data1 == self.data1
				assert data2 == self.data2

	def test_interleaved(self, tmp_pathplus: PathPlus):
		# Verify that (when the ZipFile is in control of creating file objects)
		# multiple open() calls can be made without interfering with each other.
		for f in get_files(tmp_pathplus):
			self.make_test_archive(f)
			with ZipFile(f, mode='r') as zipf:
				with zipf.open("ones") as zopen1:
					data1 = zopen1.read(500)
					with zipf.open("twos") as zopen2:
						data2 = zopen2.read(500)
						data1 += zopen1.read()
						data2 += zopen2.read()
				assert data1 == self.data1
				assert data2 == self.data2

	def test_read_after_close(self, tmp_pathplus: PathPlus):
		for f in get_files(tmp_pathplus):
			self.make_test_archive(f)
			with contextlib.ExitStack() as stack:
				with ZipFile(f, 'r') as zipf:
					zopen1 = stack.enter_context(zipf.open("ones"))
					zopen2 = stack.enter_context(zipf.open("twos"))
				data1 = zopen1.read(500)
				data2 = zopen2.read(500)
				data1 += zopen1.read()
				data2 += zopen2.read()
			assert data1 == self.data1
			assert data2 == self.data2

	def test_read_after_write(self, tmp_pathplus: PathPlus):
		for f in get_files(tmp_pathplus):
			with ZipFile(f, 'w', zipfile.ZIP_DEFLATED) as zipf:
				zipf.writestr("ones", self.data1)
				zipf.writestr("twos", self.data2)
				with zipf.open("ones") as zopen1:
					data1 = zopen1.read(500)
			assert data1 == self.data1[:500]
			with ZipFile(f, 'r') as zipf:
				data1 = zipf.read("ones")
				data2 = zipf.read("twos")
			assert data1 == self.data1
			assert data2 == self.data2

	def test_write_after_read(self, tmp_pathplus: PathPlus):
		for f in get_files(tmp_pathplus):
			with ZipFile(f, 'w', zipfile.ZIP_DEFLATED) as zipf:
				zipf.writestr("ones", self.data1)
				with zipf.open("ones") as zopen1:
					zopen1.read(500)
					zipf.writestr("twos", self.data2)
			with ZipFile(f, 'r') as zipf:
				data1 = zipf.read("ones")
				data2 = zipf.read("twos")
			assert data1 == self.data1
			assert data2 == self.data2

	def test_write_while_reading(self, tmp_pathplus: PathPlus):
		with ZipFile(tmp_pathplus / TESTFN2, 'w', zipfile.ZIP_DEFLATED) as zipf:
			zipf.writestr("ones", self.data1)
		with ZipFile(tmp_pathplus / TESTFN2, 'a', zipfile.ZIP_DEFLATED) as zipf:
			with zipf.open("ones", 'r') as r1:
				data1 = r1.read(500)
				with zipf.open("twos", 'w') as w1:
					w1.write(self.data2)
				data1 += r1.read()
		assert data1 == self.data1
		with ZipFile(tmp_pathplus / TESTFN2) as zipf:
			assert zipf.read("twos") == self.data2


class TestWithDirectory:

	def test_extract_dir(self, tmp_pathplus: PathPlus):
		with ZipFile(findfile("zipdir.zip")) as zipf:
			zipf.extractall(tmp_pathplus / TESTFN2)
		assert os.path.isdir(tmp_pathplus / TESTFN2 / 'a')
		assert os.path.isdir(tmp_pathplus / TESTFN2 / 'a' / 'b')
		assert os.path.exists(tmp_pathplus / TESTFN2 / 'a' / 'b' / 'c')

	def test_bug_6050(self, tmp_pathplus: PathPlus):
		# Extraction should succeed if directories already exist
		(tmp_pathplus / TESTFN2 / 'a').mkdir(parents=True)
		self.test_extract_dir(tmp_pathplus)

	def test_write_dir(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		dirpath = tmp_pathplus / TESTFN2 / 'x'
		dirpath.mkdir(parents=True)
		mode = os.stat(dirpath).st_mode & 0xFFFF
		with ZipFile(testfn, 'w') as zipf:
			zipf.write(dirpath)
			zinfo = zipf.filelist[0]
			assert zinfo.filename.endswith("/x/")
			assert zinfo.external_attr == (mode << 16) | 0x10
			zipf.write(dirpath, 'y')
			zinfo = zipf.filelist[1]
			assert zinfo.filename, "y/"
			assert zinfo.external_attr == (mode << 16) | 0x10
		with ZipFile(testfn, 'r') as zipf:
			zinfo = zipf.filelist[0]
			assert zinfo.filename.endswith("/x/")
			assert zinfo.external_attr == (mode << 16) | 0x10
			zinfo = zipf.filelist[1]
			assert zinfo.filename, "y/"
			assert zinfo.external_attr == (mode << 16) | 0x10
			target = os.path.join(tmp_pathplus, TESTFN2, "target")
			os.mkdir(target)
			zipf.extractall(target)
			assert os.path.isdir(os.path.join(target, 'y'))
			assert len(os.listdir(target)) == 2

	def test_writestr_dir(self, tmp_pathplus: PathPlus, testfn: PathPlus):
		(tmp_pathplus / TESTFN2 / 'x').mkdir(parents=True)

		with ZipFile(testfn, 'w') as zipf:
			zipf.writestr("x/", b'')
			zinfo = zipf.filelist[0]
			assert zinfo.filename == "x/"
			assert zinfo.external_attr == (0o40775 << 16) | 0x10
		with ZipFile(testfn, 'r') as zipf:
			zinfo = zipf.filelist[0]
			assert zinfo.filename.endswith("x/")
			assert zinfo.external_attr == (0o40775 << 16) | 0x10
			target = os.path.join(tmp_pathplus / TESTFN2, "target")
			os.mkdir(target)
			zipf.extractall(target)
			assert os.path.isdir(os.path.join(target, 'x'))
			assert os.listdir(target) == ['x']
