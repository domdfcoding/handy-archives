# 3rd party
import pytest
from domdf_python_tools.paths import PathPlus, TemporaryPathPlus

# this package
from handy_archives import TarFile
from handy_archives.testing import ArchiveFileRegressionFixture


@pytest.fixture(scope="session")
def example_tarfile():
	with TemporaryPathPlus() as tmp_pathplus:
		with TarFile.open(tmp_pathplus / "example.tar", mode='w') as tarfile:

			tarfile.add(PathPlus(__file__).parent / "Hams_Hall.jpg", arcname="Hams_Hall.jpg")

			(tmp_pathplus / "text_file.md").write_text("# Example\n\nThis is an example text file")
			tarfile.add(tmp_pathplus / "text_file.md", arcname="text_file.md")

		yield tmp_pathplus / "example.tar"


def test_extractfile(example_tarfile: PathPlus):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		assert tarfile.read_text("text_file.md") == "# Example\n\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		with tarfile.extractfile("text_file.md") as fp:
			assert fp.read() == b"# Example\n\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		with pytest.raises(FileNotFoundError, match="foo.py"):
			tarfile.extractfile("foo.py")


def test_read_text(example_tarfile: PathPlus):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		assert tarfile.read_text("text_file.md") == "# Example\n\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		info = tarfile.getmember("text_file.md")
		assert tarfile.read_text(info) == "# Example\n\nThis is an example text file"


def test_read_bytes(example_tarfile: PathPlus):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		assert tarfile.read_bytes("text_file.md") == b"# Example\n\nThis is an example text file"

	with TarFile.open(example_tarfile, 'r') as tarfile:
		info = tarfile.getmember("text_file.md")
		assert tarfile.read_bytes(info) == b"# Example\n\nThis is an example text file"


def test_archive_regression(example_tarfile: PathPlus, archive_regression: ArchiveFileRegressionFixture):
	with TarFile.open(example_tarfile, 'r') as tarfile:
		archive_regression.check_archive(tarfile, "text_file.md")
		archive_regression.check_archive_binary(tarfile, "Hams_Hall.jpg")
