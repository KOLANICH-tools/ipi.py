import csv
import typing
from io import IOBase, StringIO
from pathlib import Path, PurePath

from .deps.fetchers import DummyFetcher, Source, SourceFetcher
from .utils import canonicalizePackageName


class Package:
	__slots__ = ("name", "fetcher")

	def __init__(self, name: str, fetcher: Source = Source.git) -> None:
		self.name = name
		self.fetcher = fetcher

	def __repr__(self) -> str:
		return self.__class__.__name__ + "(" + repr(self.name) + ", " + repr(self.fetcher) + ")"


class LookupResult:
	__slots__ = ("pkg", "regPath")

	def __init__(self, pkg: Package, regPath: typing.Tuple["IRegistry"]) -> None:
		self.pkg = pkg
		self.regPath = regPath

	def __repr__(self) -> str:
		return self.__class__.__name__ + "(" + repr(self.pkg) + ", " + repr(self.regPath) + ")"


class IRegistry:
	"""An abstract interface for a registry. Each registry MUST have a human-readable name in order to allow a user to debug the issues more easy."""

	__slots__ = ("name",)

	def __init__(self, name: str) -> None:
		self.name = name

	def lookup(self, k: str) -> LookupResult:
		raise NotImplementedError


def derivePackageNameFromURI(uri: str) -> str:
	uP = PurePath(uri)
	pkgName = uP.name
	if pkgName.lower().endswith(".git"):
		pkgName = pkgName[:-4]
	return pkgName


class Registry(IRegistry):
	__slots__ = ("reg",)

	def __init__(self, name: str, reg: typing.Mapping[str, Package]) -> None:
		super().__init__(name)
		self.reg = reg

	def lookup(self, k: str) -> LookupResult:
		return LookupResult(self.reg[canonicalizePackageName(k)], (self,))

	@classmethod
	def fromCSV(cls, regCSV: typing.Union[Path, str, typing.Iterable[str]], name: str = None) -> "Registry":
		if isinstance(regCSV, Path):
			if name is None:
				name = str(regCSV.resolve().absolute())
			regCSV = regCSV.read_text()

		if name is None:
			raise ValueError("an unique must be provided when creating a registry not from file")

		if isinstance(regCSV, str):
			regCSV = regCSV.splitlines()

		dic = {}
		for el in csv.DictReader((l for l in regCSV if not l.startswith("#")), dialect=csv.excel_tab):
			#print(el)
			el = {k: v for (k, v) in el.items() if v}

			pkgName = el.get("name", None)
			if not pkgName:
				pkgName = derivePackageNameFromURI(el["repo"])

			pkgName = canonicalizePackageName(pkgName)

			repo = el.get("repo", None)
			fetcherType = el.get("fetcher", None)

			if repo:
				if fetcherType:
					fetcherType = Source[fetcherType]
				else:
					fetcherType = Source.git

				fetcher = SourceFetcher(fetcherType, repo, el.get("subDir", None), el.get("refSpec", None), int(el.get("depth", 1)))
			else:
				fetcherType = Source[fetcherType]
				fetcher = DummyFetcher(fetcherType)

			dic[pkgName] = Package(pkgName, fetcher)

		return cls(name, dic)

	def emitConfigRecords(self, postProcessor=lambda r, rec: rec):
		for packageName, p in self.reg.items():
			url = p.repo
			if url.endswith(".git"):
				url = url[: -len(".git")]
			rec = {"repo": url}
			derivedName = derivePackageNameFromURI(url)
			if p.name != derivedName:
				rec["name"] = p.name

			newRec = postProcessor(p, rec)
			if newRec:
				yield rec

	def toCSV(self, postProcessor=lambda r, rec: rec, outputStream: typing.Optional[IOBase] = None) -> typing.Optional[str]:
		if outputStream is None:
			with StringIO() as f:
				self.toCSV(postProcessor=postProcessor, outputStream=f)
				return f.getvalue()

		names = ("name", "repo")
		dw = csv.DictWriter(outputStream, fieldnames=names, dialect=csv.excel_tab)

		dw.writeheader()
		dw.writerows(self.emitConfigRecords(postProcessor))

	def __repr__(self) -> str:
		return self.__class__.__name__ + "<" + repr(self.name) + ">"


class CompoundRegistry(IRegistry):
	__slots__ = ("children",)

	def __init__(self, name: str, children: typing.Mapping[str, IRegistry]) -> None:
		super().__init__(name)
		self.children = children

	def lookup(self, k: str) -> LookupResult:
		for child in self.children.values():
			try:
				res = child.lookup(k)
				res.regPath = (self,) + res.regPath
				return res
			except KeyError:
				continue
		raise KeyError(k)

	@classmethod
	def fromCSVDir(cls, name: str, csvDir: Path, nameGen: typing.Optional[typing.Callable] = None) -> "CompoundRegistry":
		if nameGen is None:

			def nameGen(x):
				return None

		return cls(name, {regF.stem: Registry.fromCSV(regF, name=nameGen(regF)) for regF in csvDir.glob("*.tsv")})

	def __repr__(self) -> str:
		return self.__class__.__name__ + "<" + repr(self.name) + ", " + repr(self.children.keys()) + ">"


def initRegistries() -> CompoundRegistry:
	from .defaultPetnames import builtInRegistries

	regs = {
		"builtin": builtInRegistries,
	}

	from .settings import privateRegistriesDir, reposRoot

	if privateRegistriesDir is not None:
		privateReg = CompoundRegistry.fromCSVDir("private", privateRegistriesDir)
		tufRegsDict = {}

		try:
			from .repos.tuf.RepoManager import RepoManager
		except ImportError:
			pass
		else:
			m = RepoManager(reposRoot)
			for repoPetName in m:
				print(repoPetName)
				repo = m[repoPetName]
				repo.update()
				tufRegsDict[repoPetName] = repo.toRegistry()

			userTufReg = CompoundRegistry("tuf", tufRegsDict)

			userReg = CompoundRegistry(
				"user",
				{
					privateReg.name: privateReg,
					userTufReg.name: userTufReg,
				},
			)
			regs[userReg.name] = userReg

	return CompoundRegistry("unified", regs)
