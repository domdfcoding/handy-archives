# stdlib
import os
import unittest
from typing import Callable, no_type_check


@no_type_check
def requires_gzip(reason="requires gzip"):
	try:
		# stdlib
		import gzip
	except ImportError:
		gzip = None
	return unittest.skipUnless(gzip, reason)


@no_type_check
def requires_zlib(reason="requires zlib"):
	try:
		# stdlib
		import zlib
	except ImportError:
		zlib = None
	return unittest.skipUnless(zlib, reason)


@no_type_check
def requires_bz2(reason="requires bz2"):
	try:
		# stdlib
		import bz2
	except ImportError:
		bz2 = None
	return unittest.skipUnless(bz2, reason)


@no_type_check
def requires_lzma(reason="requires lzma"):
	try:
		# stdlib
		import lzma
	except ImportError:
		lzma = None
	return unittest.skipUnless(lzma, reason)


def skip_unless_symlink(test: Callable):
	"""
	Skip decorator for tests that require symlinks.
	"""

	msg = "Requires functional symlink implementation"
	return test if CAN_SYMLINK else unittest.skip(msg)(test)


# Filename used for testing
if os.name == "java":
	# Jython disallows @ in module names
	TESTFN = "$test"
else:
	TESTFN = "@test"

# Disambiguate TESTFN for parallel testing, while letting it remain a valid
# module name.
TESTFN = f"{TESTFN}_{os.getpid()}_tmp"

symlink_path = TESTFN + "can_symlink"

try:
	os.symlink(TESTFN, symlink_path)
	CAN_SYMLINK = True
except (OSError, NotImplementedError, AttributeError):
	CAN_SYMLINK = False
else:
	os.remove(symlink_path)
