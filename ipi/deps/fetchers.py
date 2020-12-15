import typing
from enum import IntEnum

from .git import fetchUsingGit
from .hg import fetchUsingMercurial


class Source(IntEnum):
	none = 0
	system = 1
	pip = 2
	git = 3
	hg = 4


Source.none.__doc__ = "Undefined fetcher"
Source.system.__doc__ = "Package must be already installed in the system"
Source.pip.__doc__ = "Install a wheel from pip"
Source.git.__doc__ = "Fetch source from a git repo"
Source.hg.__doc__ = "Fetch source from a hg repo"


fetchers = {
	Source.git: fetchUsingGit,
	Source.hg: fetchUsingMercurial,
}


class Fetcher:
	__slots__ = ()


class DummyFetcher(Fetcher):
	__slots__ = ("type",)

	def __init__(self, tp: Source) -> None:
		self.type = tp

	def __repr__(self) -> str:
		return self.__class__.__name__ + "(" + repr(self.type) + ")"


class SourceFetcher(DummyFetcher):
	__slots__ = (
		"repo",
		"subDir",
		"depth",
		"refSpec",
	)

	def __init__(self, tp: Source, repo: str, subDir: typing.Optional[str] = None, refSpec: typing.Optional[str] = None, depth: int = 1) -> None:
		super().__init__(tp)
		self.repo = repo
		self.subDir = subDir
		self.refSpec = refSpec
		self.depth = depth

	def __repr__(self) -> str:
		return self.__class__.__name__ + "(" + repr(self.repo) + (", subDir=" + repr(self.subDir) if self.subDir else "") + (", refSpec=" + repr(self.refSpec) if self.refSpec else "") + (", depth=" + repr(self.depth) if self.depth != 1 else "") + ")"
