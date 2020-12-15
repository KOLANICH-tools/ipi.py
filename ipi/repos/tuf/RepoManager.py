from pathlib import Path

from tuft.RepoManager import RepoManager as TuftRepoManager

from ...settings import reposRoot as defaultReposRoot
from .Repo import Repo
from .RepoBuilder import *


class RepoManager(TuftRepoManager):
	__slots__ = ()

	REPO_CLASS = Repo

	def __init__(self, reposRoot: Path = defaultReposRoot) -> None:
		super().__init__(reposRoot)
