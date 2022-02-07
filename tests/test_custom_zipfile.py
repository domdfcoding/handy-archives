# stdlib
import datetime
import os
from typing import IO

# 3rd party
import pytest
from domdf_python_tools.paths import PathPlus

# this package
from handy_archives import ZipFile
from handy_archives.testing import ArchiveFileRegressionFixture


@pytest.fixture()
def example_zipfile(tmp_pathplus: PathPlus):
	with ZipFile(tmp_pathplus / "example.tar", mode='w') as zip_file:

		zip_file.write(PathPlus(__file__).parent / "Hams_Hall.jpg", arcname="Hams_Hall.jpg")

		(tmp_pathplus / "text_file.md").write_text("# Example\r\n\r\nThis is an example text file")
		zip_file.write(tmp_pathplus / "text_file.md", arcname="text_file.md")

	yield tmp_pathplus / "example.tar"


def test_encrypted(tmp_pathplus: PathPlus):

	data = (
			b'PK\x03\x04\x14\x00\x01\x00\x00\x00n\x92i.#y\xef?&\x00\x00\x00\x1a\x00'
			b'\x00\x00\x08\x00\x00\x00test.txt\xfa\x10\xa0gly|\xfa-\xc5\xc0=\xf9y'
			b'\x18\xe0\xa8r\xb3Z}Lg\xbc\xae\xf9|\x9b\x19\xe4\x8b\xba\xbb)\x8c\xb0\xdbl'
			b'PK\x01\x02\x14\x00\x14\x00\x01\x00\x00\x00n\x92i.#y\xef?&\x00\x00\x00'
			b'\x1a\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x01\x00 \x00\xb6\x81'
			b'\x00\x00\x00\x00test.txtPK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x006\x00'
			b'\x00\x00L\x00\x00\x00\x00\x00'
			)

	fp: IO[bytes]

	with open(tmp_pathplus / "test.zip", "wb") as fp:
		fp.write(data)

	with ZipFile(tmp_pathplus / "test.zip", 'r') as zipfile:

		with zipfile.extractfile("test.txt", pwd="python") as fp:
			assert fp.read() == b'zipfile.py encryption test'

		with zipfile.extractfile("test.txt", pwd=b"python") as fp:
			assert fp.read() == b'zipfile.py encryption test'

		assert zipfile.read_text("test.txt", pwd="python") == "zipfile.py encryption test"
		assert zipfile.read_text("test.txt", pwd=b"python") == "zipfile.py encryption test"

		assert zipfile.read_bytes("test.txt", pwd="python") == b'zipfile.py encryption test'
		assert zipfile.read_bytes("test.txt", pwd=b"python") == b'zipfile.py encryption test'


def test_extractfile(example_zipfile: PathPlus):
	with ZipFile(example_zipfile, 'r') as zip_file:
		assert zip_file.read_text("text_file.md") == "# Example\r\n\r\nThis is an example text file"
		assert zip_file.read_text("text_file.md", normalize_nl=True) == "# Example\n\nThis is an example text file"

	with ZipFile(example_zipfile, 'r') as zip_file:
		with zip_file.extractfile("text_file.md") as fp:
			assert fp.read() == b"# Example\r\n\r\nThis is an example text file"

	with ZipFile(example_zipfile, 'r') as zip_file:
		with pytest.raises(FileNotFoundError, match="foo.py"):
			zip_file.extractfile("foo.py")


def test_read_text(example_zipfile: PathPlus):
	with ZipFile(example_zipfile, 'r') as zip_file:
		assert zip_file.read_text("text_file.md") == "# Example\r\n\r\nThis is an example text file"
		assert zip_file.read_text("text_file.md", normalize_nl=True) == "# Example\n\nThis is an example text file"

		info = zip_file.getinfo("text_file.md")
		assert zip_file.read_text(info) == "# Example\r\n\r\nThis is an example text file"


def test_write_file(example_zipfile: PathPlus, tmp_pathplus: PathPlus):
	my_file = tmp_pathplus / "my_file.txt"
	my_file.write_text("# Example2\n\nThis is another example text file")

	with ZipFile(example_zipfile, 'w') as zip_file:
		zip_file.write_file(my_file, arcname=my_file.name)
		zip_file.write_file(my_file, arcname=PathPlus("my_file2.md"), mtime=datetime.datetime(1996, 10, 13, 2, 20))

		with pytest.raises(IsADirectoryError, match="'ZipFile.write_file' only supports files"):
			zip_file.write_file(tmp_pathplus)

		with zip_file.open("foo.py", 'w') as fp:
			fp.write(b"Hello World")

			with pytest.raises(ValueError, match="Can't write to ZIP archive while an open writing handle exists"):
				zip_file.write_file(my_file, arcname="my_file3.md")

	with ZipFile(example_zipfile, 'r') as zip_file:
		assert zip_file.read_text("my_file.txt") == "# Example2\n\nThis is another example text file"

		info = zip_file.getinfo("my_file2.md")
		assert info.date_time == (1996, 10, 13, 2, 20, 0)
		assert zip_file.read_text(info) == "# Example2\n\nThis is another example text file"

		assert zip_file.namelist() == ["my_file.txt", "my_file2.md", "foo.py"]


def test_write_file_arcname_none(example_zipfile: PathPlus, tmp_pathplus: PathPlus):
	my_file = tmp_pathplus / "my_file.txt"
	my_file.write_text("# Example2\n\nThis is another example text file")

	with ZipFile(example_zipfile, 'w') as zip_file:
		zip_file.write_file(my_file, arcname=None)

	with ZipFile(example_zipfile, 'r') as zip_file:
		# With arcname=None the file has the same path as on the filesystem.
		assert zip_file.read_text(
				os.path.splitdrive(my_file.as_posix())[1][1:]
				) == "# Example2\n\nThis is another example text file"

	my_file = tmp_pathplus / "my_file.txt"
	my_file.write_text("# Example2\n\nThis is another example text file")

	with ZipFile(example_zipfile, 'w') as zip_file:
		zip_file.write_file(my_file, arcname=None, mtime=datetime.datetime(1996, 10, 13, 2, 20))

	with ZipFile(example_zipfile, 'r') as zip_file:
		# breakpoint()
		# With arcname=None the file has the same path as on the filesystem.
		assert zip_file.read_text(
				os.path.splitdrive(my_file.as_posix())[1][1:]
				) == "# Example2\n\nThis is another example text file"


def test_read_bytes(example_zipfile: PathPlus):
	with ZipFile(example_zipfile, 'r') as zip_file:
		assert zip_file.read_bytes("text_file.md") == b"# Example\r\n\r\nThis is an example text file"

		info = zip_file.getinfo("text_file.md")
		assert zip_file.read_bytes(info) == b"# Example\r\n\r\nThis is an example text file"


def test_archive_regression(example_zipfile: PathPlus, archive_regression: ArchiveFileRegressionFixture):
	with ZipFile(example_zipfile, 'r') as zip_file:
		archive_regression.check_archive(zip_file, "text_file.md")
		archive_regression.check_archive_binary(zip_file, "Hams_Hall.jpg")
