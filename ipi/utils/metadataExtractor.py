#!/usr/bin/env python3
import ast
import platform
import re
import sys
import typing
from pathlib import Path
from warnings import warn

from . import canonicalizePackageName

try:
	from packaging.requirements import Requirement

	def canonicalizedRequirement(rStr: str) -> Requirement:
		r = Requirement(rStr)
		r.name = canonicalizePackageName(r.name)
		return r

except ImportError:
	Requirement = None
	canonicalizedRequirement = None

try:
	import tomllib
except ImportError:
	try:
		import tomli as tomllib
	except ImportError:
		tomllib = None

try:
	from setuptools.config import read_configuration as parseSetupCfg
except ImportError:
	import configparser

	def parseSetupCfg(setupCfgPath: Path):
		res = configparser.ConfigParser()
		res.read(setupCfgPath)
		return res


__all__ = ("extractMetadata", "MetadataExtractionException")

# pylint:disable=unused-argument,import-outside-toplevel

PyprojectTOML_T = typing.Dict[str, typing.Union[str, int, list]]


validPackageNameRx = re.compile("^[\\.\\w-]+$")


class MetadataExtractionException(ValueError):
	__slots__ = ()


class MetadataExtractor:
	__slots__ = ()

	DEBUG = False

	@property
	def name(self):
		name = self._getName()
		if not validPackageNameRx.match(name):
			raise MetadataExtractionException("The package name is invalid: ", name, validPackageNameRx)
		return name

	@property
	def buildDeps(self):
		bd = self._getBuildDeps()
		res = []
		for el in bd:
			#print(repr(el))
			res.append(canonicalizedRequirement(el))
		return res

	@property
	def deps(self):
		d = self._getDeps()
		res = []
		for el in d:
			#print(repr(el))
			res.append(canonicalizedRequirement(el))
		return res


class PEP517MetadataExtractor(MetadataExtractor):
	__slots__ = ("toolSpecificDic", "child")

	def __init__(self, pyproject: PyprojectTOML_T):
		self.child = None
		self.toolSpecificDic = pyproject.get("build-system", None)
		if not isinstance(self.toolSpecificDic, dict):
			raise MetadataExtractionException("PEP 517 metadata is not present")

	def _getName(self):
		return self.child._getName()

	def _getDeps(self):
		return self.child._getDeps()

	@property
	def buildBackend(self):
		return self.toolSpecificDic.get("build-backend", "setuptools.build_meta").split(".")

	def _getBuildDeps(self):
		return self.toolSpecificDic.get("requires", [])


def tryExtractPEP517AndPEP621Metadata(pyproject):
	pep517 = PEP517MetadataExtractor(pyproject)

	try:
		pep517.child = PEP621MetadataExtractor(pyproject)
	except MetadataExtractionException as ex:
		print(str(ex))

	return pep517


def extractMetadata(rootDir: Path):
	tomlPath = Path(rootDir / "pyproject.toml")
	pep517 = None
	backend = None
	buildBackend = None
	pyproject = None

	def fallBackToSetuptools(msg: str):
		nonlocal buildBackendName
		buildBackendName = "setuptools"
		print(msg + ", falling back to", buildBackendName, file=sys.stderr)

	if tomllib:
		if tomlPath.is_file():
			with tomlPath.open("rb") as f:
				pyproject = tomllib.load(f)

			try:
				pep517 = tryExtractPEP517AndPEP621Metadata(pyproject)
			except MetadataExtractionException as e:
				pep517 = None
				fallBackToSetuptools("error extracting metadata from pyproject.toml: " + str(e))
			else:
				buildBackendName = pep517.buildBackend[0]
		else:
			fallBackToSetuptools("pyproject.toml is not present")
	else:
		fallBackToSetuptools("`tomllib`/`tomli` are not present")

	print("Build backend used: ", buildBackendName, file=sys.stderr)

	if not pep517 or pep517.child is None:  # Not PEP 621
		if pep517:
			print("pep517.child", pep517.child)
		else:
			print("not pep517")
		backend = toolSpecificExtractors[buildBackendName](pyproject, rootDir)

	if pep517:
		if backend is not None:
			pep517.child = backend
		backend = pep517

	return backend


class PEP621MetadataExtractor(MetadataExtractor):
	__slots__ = ("toolSpecificDic",)

	def __init__(self, pyproject: PyprojectTOML_T):
		self.toolSpecificDic = pyproject.get("project", None)
		if self.__class__.DEBUG:
			print("self.toolSpecificDic", self.toolSpecificDic)

		if not isinstance(self.toolSpecificDic, dict):
			raise MetadataExtractionException("PEP 621 metadata is not present")

	def _getBuildDeps(self):
		raise NotImplementedError

	def _getName(self):
		return self.toolSpecificDic.get("name", None)

	def _getDeps(self):
		return self.toolSpecificDic.get("dependencies", [])


class FlitMetadataExtractor(MetadataExtractor):
	__slots__ = ("toolSpecificDic",)

	def __init__(self, pyproject: PyprojectTOML_T, rootDir: Path):
		self.toolSpecificDic = None
		tool = pyproject.get("tool", None)
		if isinstance(tool, dict):
			flit = tool.get("flit", None)
			if isinstance(flit, dict):
				self.toolSpecificDic = flit

		if self.toolSpecificDic is None:
			raise MetadataExtractionException("Flit metadata is not present")

	def _getName(self):
		metadata = self.toolSpecificDic.get("metadata", None)
		if isinstance(metadata, dict):
			name = metadata.get("dist-name", None)
			if name is None:
				name = metadata.get("module", None)
			if name:
				return name

	def _getBuildDeps(self):
		raise NotImplementedError

	def _getDeps(self):
		raise NotImplementedError


class PoetryMetadataExtractor(MetadataExtractor):
	__slots__ = ("toolSpecificDic",)

	def __init__(self, pyproject: PyprojectTOML_T, rootDir: Path):
		self.toolSpecificDic = None

		tool = pyproject.get("tool", None)
		if isinstance(tool, dict):
			poetry = tool.get("poetry", None)
			if isinstance(poetry, dict):
				self.toolSpecificDic = poetry

		if self.toolSpecificDic is None:
			raise MetadataExtractionException("Poetry metadata is not present")

	def _getName(self):
		name = self.toolSpecificDic.get("name", None)
		if name:
			return name

	def _getBuildDeps(self):
		raise NotImplementedError

	def _getDeps(self):
		return sorted(set(self.toolSpecificDic.get("dependencies", {})) - {"python"})


class PDMMetadataExtractor(MetadataExtractor):
	__slots__ = ()

	def __init__(self, pyproject: PyprojectTOML_T, rootDir: Path):
		self.toolSpecificDic = None

		tool = pyproject.get("tool", None)
		if isinstance(tool, dict):
			pdm = tool.get("pdm", None)
			if isinstance(pdm, dict):
				self.toolSpecificDic = pdm

		if self.toolSpecificDic is None:
			raise MetadataExtractionException("PDM metadata is not present")

	def _getName(self):
		name = pdm.get("name", None)
		if name:
			return name

	def _getBuildDeps(self):
		raise NotImplementedError

	def _getDeps(self):
		raise NotImplementedError


class SetuptoolsMetadataExtractor(MetadataExtractor):
	__slots__ = (
		"setupCfg",
		"setupPy",
	)

	def __init__(self, pyproject: PyprojectTOML_T, rootDir: Path):
		self.setupCfg = None  # type: typing.Optional[SetuptoolsSetupCfgMetadataExtractor]
		self.setupPy = None  # type: typing.Optional[SetuptoolsSetupPyMetadataExtractor]

		setupCfgPath = Path(rootDir / "setup.cfg")
		setupPyPath = Path(rootDir / "setup.py")

		if not setupCfgPath.is_file() and not setupPyPath.is_file():
			raise MetadataExtractionException("setuptools metadata is not present")

		if setupCfgPath.is_file():
			self.setupCfg = SetuptoolsSetupCfgMetadataExtractor(setupCfgPath)

		if setupPyPath.is_file():
			self.setupPy = SetuptoolsSetupPyMetadataExtractor(setupPyPath)

	def _getName(self):
		res = None
		if self.setupCfg:
			res = self.setupCfg._getName()

		if not res and self.setupPy:
			res = self.setupPy._getName()

		return res

	def _getBuildDeps(self):
		res = None
		if self.setupCfg:
			res = self.setupCfg._getBuildDeps()

		if not res and self.setupPy:
			res = self.setupPy._getBuildDeps()

		return res

	def _getDeps(self):
		res = None
		if self.setupCfg:
			res = self.setupCfg._getDeps()

		if not res and self.setupPy:
			res = self.setupPy._getDeps()

		return res


class SetuptoolsSetupCfgMetadataExtractor(SetuptoolsMetadataExtractor):
	__slots__ = ("toolSpecificDic",)

	def __init__(self, setupCfgPath: Path):
		self.toolSpecificDic = parseSetupCfg(setupCfgPath)

	def _getName(self):
		try:
			return self.toolSpecificDic["metadata"]["name"]
		except KeyError:
			return None

	@classmethod
	def _removeTrailingComment(cls, el):
		try:
			return el[: el.rindex("#")]
		except ValueError:
			return el

	@classmethod
	def _removeTrailingComments(cls, els):
		res = []
		for el in els:
			res.append(cls._removeTrailingComment(el))
		return res

	def _getBuildDeps(self):
		try:
			return self.__class__._removeTrailingComments(self.toolSpecificDic["options"]["setup_requires"])
		except KeyError:
			return []

	def _getDeps(self):
		try:
			return self.__class__._removeTrailingComments(self.toolSpecificDic["options"]["install_requires"])
		except KeyError:
			return []


class SetuptoolsSetupPyMetadataExtractor(SetuptoolsMetadataExtractor):
	__slots__ = ("ast", "setupCall", "keywordsDict", "constantFoldingDict")

	def __init__(self, setupPyPath: Path):
		self.ast = ast.parse(setupPyPath.read_text())
		self.constantFoldingDict = None

		try:
			from peval.highlevelapi import _run_components
		except ImportError:
			warn("peval is not installed, constant folding is not available")
		else:
			self.ast, self.constantFoldingDict = _run_components(self.ast, {"sys": sys, "platform": platform})

			if self.__class__.DEBUG:
				from pprint import pprint

				pprint(self.constantFoldingDict)

		if self.__class__.DEBUG:
			if hasattr(ast, "fix_missing_locations"):
				ast.fix_missing_locations(self.ast)

			print(ast.dump(self.ast))
			try:
				print(ast.unparse(self.ast))
			except AttributeError:
				pass

		self.setupCall = self.__class__.findSetupCall(self.ast)
		if self.setupCall:
			self.keywordsDict = self.__class__.keywordsToDict(self.setupCall.keywords)
		else:
			self.keywordsDict = {}

	@classmethod
	def isSetupCall(cls, n) -> bool:
		if isinstance(n, ast.Call):
			return cls.isSetupFunc(n.func)
		return False

	@classmethod
	def isSetupFunc(cls, f: ast.AST) -> bool:
		if cls.isAttrributeSetupFunc(f) or cls.isBareSetupFunc(f):
			return True

		return False

	SETUPTOOLS_MODULE_NAME = "setuptools"
	SETUP_FUNC_NAME = "setup"

	@classmethod
	def isBareSetupFunc(cls, f) -> bool:
		return isinstance(f, ast.Name) and f.id == cls.SETUP_FUNC_NAME

	@classmethod
	def isAttrributeSetupFunc(cls, f) -> bool:
		return isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == cls.SETUPTOOLS_MODULE_NAME and f.attr == cls.SETUP_FUNC_NAME

	@classmethod
	def findSetupCall(cls, a):
		for n in ast.walk(a):
			if cls.isSetupCall(n):
				return n

		return None

	@classmethod
	def keywordsToDict(cls, keywords) -> dict:
		return {kw.arg: kw.value for kw in keywords}

	def astNodeToValue(self, el: ast.AST):
		if isinstance(el, ast.Name):
			if self.constantFoldingDict is not None:
				return self.constantFoldingDict[el.id]
			else:
				raise NotImplementedError("You need `peval` to correctly parse metadata from this `setup.py`, since it references a var")
		if isinstance(el, ast.Subscript):
			d = self.astNodeToValue(el.value)
			return d[self.astNodeToValue(el.slice)]
		if isinstance(el, ast.AST):
			return ast.literal_eval(el)
		return el

	def getSetupKeyword(self, name: str):
		return self.astNodeToValue(self.keywordsDict[name])

	def _getName(self):
		res = self.getSetupKeyword("name")
		if not isinstance(res, str):
			raise ValueError("`name` is not a `str`")
		return res

	def _getArray(self, name: str, tp: type):
		try:
			res = self.getSetupKeyword(name)
		except KeyError:
			return ()

		if not isinstance(res, (list, tuple, set)):
			raise ValueError("`" + name + "` is not a `list`", res)

		for i, el in enumerate(res):
			if not isinstance(el, tp):
				raise ValueError("element is not of right type", name, i, el)

		return res

	def _getBuildDeps(self):
		return self._getArray("setup_requires", str)

	def _getDeps(self):
		return self._getArray("install_requires", str)


toolSpecificExtractors = {
	"setuptools": SetuptoolsMetadataExtractor,
	"flit_core": FlitMetadataExtractor,
	"poetry": PoetryMetadataExtractor,
	"pdm": PDMMetadataExtractor,
}


def main():
	if len(sys.argv) > 1:
		p = sys.argv[1]
	else:
		p = "."

	p = Path(p)
	md = extractMetadata(p)

	print(md.name, file=sys.stdout)
	print(md.buildDeps, file=sys.stdout)
	print(md.deps, file=sys.stdout)


if __name__ == "__main__":
	main()
