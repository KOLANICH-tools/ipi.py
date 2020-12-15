import typing
from pathlib import Path, PurePath

from tuft.Repo import Repo as TuftRepo

from ...registries import CompoundRegistry, Registry


class Repo(TuftRepo):
	__slots__ = ()

	def __getitem__(self, k: str):
		return self._listFromPurePath(PurePath(k + ".tsv"), k)

	def _listFromPurePath(self, k: PurePath, name: str) -> Registry:
		return self._listFromPath(super().__getitem__(k), name)

	def _listFromPath(self, listPath: Path, name: str) -> Registry:
		reg = Registry.fromCSV(listPath, name)
		return reg

	def toRegistry(self) -> CompoundRegistry:
		repoPetName = self.localPath.name
		repoRegData = {}
		for filePath in self:
			if filePath.suffix.lower() == ".tsv":
				print(repr(filePath))
				listName = filePath.stem
				repoRegData[listName] = self._listFromPurePath(filePath, listName)

		return CompoundRegistry(repoPetName, repoRegData)
