# stdlib
from typing import IO

# 3rd party
import pytest
from domdf_python_tools.paths import PathPlus, TemporaryPathPlus

# this package
from handy_archives import ZipFile
from handy_archives.testing import ArchiveFileRegressionFixture


@pytest.fixture(scope="session")
def example_zipfile():
	with TemporaryPathPlus() as tmp_pathplus:
		with ZipFile(tmp_pathplus / "example.tar", mode='w') as tarfile:

			tarfile.write(PathPlus(__file__).parent / "Hams_Hall.jpg", arcname="Hams_Hall.jpg")

			(tmp_pathplus / "text_file.md").write_text("# Example\n\nThis is an example text file")
			tarfile.write(tmp_pathplus / "text_file.md", arcname="text_file.md")

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
	with ZipFile(example_zipfile, 'r') as tarfile:
		assert tarfile.read_text("text_file.md") == "# Example\n\nThis is an example text file"

	with ZipFile(example_zipfile, 'r') as tarfile:
		with tarfile.extractfile("text_file.md") as fp:
			assert fp.read() == b"# Example\n\nThis is an example text file"

	with ZipFile(example_zipfile, 'r') as tarfile:
		with pytest.raises(FileNotFoundError, match="foo.py"):
			tarfile.extractfile("foo.py")


def test_read_text(example_zipfile: PathPlus):
	with ZipFile(example_zipfile, 'r') as tarfile:
		assert tarfile.read_text("text_file.md") == "# Example\n\nThis is an example text file"

		info = tarfile.getinfo("text_file.md")
		assert tarfile.read_text(info) == "# Example\n\nThis is an example text file"


def test_read_bytes(example_zipfile: PathPlus):
	with ZipFile(example_zipfile, 'r') as tarfile:
		assert tarfile.read_bytes("text_file.md") == b"# Example\n\nThis is an example text file"

		info = tarfile.getinfo("text_file.md")
		assert tarfile.read_bytes(info) == b"# Example\n\nThis is an example text file"


def test_archive_regression(example_zipfile: PathPlus, archive_regression: ArchiveFileRegressionFixture):
	with ZipFile(example_zipfile, 'r') as tarfile:
		archive_regression.check_archive(tarfile, "text_file.md")
		archive_regression.check_archive_binary(tarfile, "Hams_Hall.jpg")
