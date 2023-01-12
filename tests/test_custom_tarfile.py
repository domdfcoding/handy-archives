# stdlib
import datetime
from typing import Iterator

# 3rd party
import pytest
from domdf_python_tools.paths import PathPlus

# this package
from handy_archives import TarFile
from handy_archives.testing import ArchiveFileRegressionFixture


@pytest.fixture()
def example_tarfile(tmp_pathplus: PathPlus) -> Iterator[PathPlus]:
	with TarFile.open(tmp_pathplus / "example.tar", mode='w') as tarfile:

		tarfile.add(PathPlus(__file__).parent / "Hams_Hall.jpg", arcname="Hams_Hall.jpg")

		(tmp_pathplus / "text_file.md").write_text("# Example\r\n\r\nThis is an example text file")
		tarfile.add(tmp_pathplus / "text_file.md", arcname="text_file.md")

	yield tmp_pathplus / "example.tar"


def test_extractfile(example_tarfile: PathPlus):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		assert tarfile.read_text("text_file.md") == "# Example\r\n\r\nThis is an example text file"
		assert tarfile.read_text("text_file.md", normalize_nl=True) == "# Example\n\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		with tarfile.extractfile("text_file.md") as fp:
			assert fp.read() == b"# Example\r\n\r\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		with pytest.raises(FileNotFoundError, match="foo.py"):
			tarfile.extractfile("foo.py")


def test_read_text(example_tarfile: PathPlus):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		assert tarfile.read_text("text_file.md") == "# Example\r\n\r\nThis is an example text file"
		assert tarfile.read_text("text_file.md", normalize_nl=True) == "# Example\n\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		info = tarfile.getmember("text_file.md")
		assert tarfile.read_text(info) == "# Example\r\n\r\nThis is an example text file"


def test_write_file(example_tarfile: PathPlus, tmp_pathplus: PathPlus):
	my_file = tmp_pathplus / "my_file.txt"
	my_file.write_text("# Example2\n\nThis is another example text file")

	with TarFile(example_tarfile, 'w') as zip_file:
		zip_file.write_file(my_file, arcname=my_file.name)
		zip_file.write_file(my_file, arcname=PathPlus("my_file2.md"), mtime=datetime.datetime(1996, 10, 13, 2, 20))

		with pytest.raises(IsADirectoryError, match="'TarFile.write_file' only supports files"):
			zip_file.write_file(tmp_pathplus)

	with TarFile(example_tarfile, 'r') as zip_file:
		assert zip_file.read_text("my_file.txt") == "# Example2\n\nThis is another example text file"

		info = zip_file.getmember("my_file2.md")
		assert info.mtime == datetime.datetime(1996, 10, 13, 2, 20).timestamp()
		assert zip_file.read_text(info) == "# Example2\n\nThis is another example text file"

		assert zip_file.getnames() == ["my_file.txt", "my_file2.md"]


def test_read_bytes(example_tarfile: PathPlus):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		assert tarfile.read_bytes("text_file.md") == b"# Example\r\n\r\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		info = tarfile.getmember("text_file.md")
		assert tarfile.read_bytes(info) == b"# Example\r\n\r\nThis is an example text file"


def test_archive_regression(example_tarfile: PathPlus, archive_regression: ArchiveFileRegressionFixture):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		archive_regression.check_archive(tarfile, "text_file.md")
		archive_regression.check_archive_binary(tarfile, "Hams_Hall.jpg")
