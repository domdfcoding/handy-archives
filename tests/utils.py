# stdlib
import os
import unittest
from typing import no_type_check


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


_can_symlink = None


def can_symlink():
	global _can_symlink
	if _can_symlink is not None:
		return _can_symlink
	symlink_path = TESTFN + "can_symlink"
	try:
		os.symlink(TESTFN, symlink_path)
		can = True
	except (OSError, NotImplementedError, AttributeError):
		can = False
	else:
		os.remove(symlink_path)
	_can_symlink = can
	return can


def skip_unless_symlink(test):
	"""Skip decorator for tests that require functional symlink"""
	ok = can_symlink()
	msg = "Requires functional symlink implementation"
	return test if ok else unittest.skip(msg)(test)


# Filename used for testing
if os.name == "java":
	# Jython disallows @ in module names
	TESTFN = "$test"
else:
	TESTFN = "@test"

# Disambiguate TESTFN for parallel testing, while letting it remain a valid
# module name.
TESTFN = f"{TESTFN}_{os.getpid()}_tmp"
