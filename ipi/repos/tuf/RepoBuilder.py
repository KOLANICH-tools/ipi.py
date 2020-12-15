from tuft.RepoBuilder import RepoBuilder as TuftRepoBuilder
from tuft.RepoBuilder import RepoSeed

from ...registries import Registry


class RepoBuilder(TuftRepoBuilder):
	def addRegistry(self, reg: Registry):
		self.userFiles[reg.name + ".tsv"] = reg.toCSV().encode("utf-8")
