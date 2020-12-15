import os
import sys
import typing
from collections import OrderedDict
from pathlib import Path

from .WithEnv import WithEnv


def dedupPreservingOrder(*args):
	dedup = OrderedDict()
	for col in args:
		if col:
			for el in col:
				dedup[el] = True

	return dedup.keys()


def normalizePathsList(classPaths):
	for f in classPaths:
		if isinstance(f, Path):
			f = str(f.absolute())
		yield f


def appendPathsList(classPaths, origClassPath: typing.Iterable[str] = ()):
	classPaths = list(classPaths)
	res = dedupPreservingOrder(list(normalizePathsList(classPaths)), origClassPath)
	return res


def getPythonPath():
	pp = os.environ.get("PYTHONPATH", None)
	if pp is not None:
		pp = pp.split(os.pathsep)
	else:
		pp = []

	return [Path(el) for el in pp]


def pathsToEnvVar(paths):
	return os.pathsep.join(str(el) for el in paths)


def cookPythonPathEnvVar(paths):
	if not paths:
		return None

	cPP = getPythonPath()
	newCPP = appendPathsList(paths, cPP)
	return pathsToEnvVar(newCPP)


def cookPythonPathEnvDict(paths):
	pp = cookPythonPathEnvVar(paths)
	if not pp:
		return None

	return {"PYTHONPATH": pp}


class WithEnv:
	__slots__ = ("patch", "backup")

	def __init__(self, **kwargs):
		self.patch = kwargs
		self.backup = None

	def __enter__(self):
		self.backup = os.environ.copy()
		os.environ.update(self.patch)
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		os.environ = self.backup


class WithPythonPath:
	__slots__ = ("patch", "backup", "we")

	def __init__(self, *args):
		self.patch = args
		self.backup = None
		self.we = None

	def __enter__(self):
		self.backup = sys.path
		ppd = cookPythonPathEnvDict(self.patch)
		sys.path = [str(el) for el in dedupPreservingOrder([Path(el).absolute() for el in self.patch], [Path(el) for el in sys.path])]
		if ppd:
			self.we = WithEnv(**ppd)
			self.we.__enter__()
			return self

	def __exit__(self, exc_type, exc_value, traceback):
		if self.backup:
			sys.path = self.backup
		if self.we:
			self.we.__exit__(exc_type, exc_value, traceback)
			self.we = None
