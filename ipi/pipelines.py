"""Single-package build and install pipeline"""

import json
import re
import sys
import typing
from collections import defaultdict
from enum import IntEnum
from functools import partial
from pathlib import Path, PurePath
from tempfile import TemporaryDirectory, mkdtemp

from .deps import sh
from .deps.fetchers import Source, SourceFetcher, fetchers
from .deps.icecream import ic
from .deps.unpin import unpinRequirement
from .tools import install
from .tools.python import python
from .tools.setup_py import wheelCmd
from .utils import pythonBuild
from .utils.CLICookie import CLICookie
from .utils.metadataExtractor import Requirement, canonicalizedRequirement, extractMetadata
from .utils.styles import styles
from .utils.WithPythonPath import cookPythonPathEnvDict

standalonePEP517Cmd = python.bake("-m", pythonBuild.__spec__.name)


def clonePackagesRepos(targetDir: Path, packagesToClone: typing.Iterable[str], registry: "IRegistry"):
	res = {}
	ignored = []

	for name in packagesToClone:
		outDir = targetDir / name
		lookupRes = registry.lookup(name).pkg
		fetcherSpec = lookupRes.fetcher

		if isinstance(fetcherSpec, SourceFetcher):
			fetcher = fetchers.get(fetcherSpec.type, None)
			if fetcher is None:
				print("fetcherSpec", fetcherSpec)
				ignored.append(lookupRes)
				continue
		else:
			print("fetcherSpec", fetcherSpec)
			ignored.append(lookupRes)
			continue

		fetcher(fetcherSpec.repo, outDir, depth=fetcherSpec.depth, refSpec=fetcherSpec.refSpec)
		if fetcherSpec.subDir:
			outDir = outDir / fetcherSpec.subDir

		res[name] = outDir

	return res, ignored


class ResolutionPrefs:
	__slots__ = ("upgrade", "resolveDeps", "forceReinstall")

	def __init__(self, upgrade: bool = False, resolveDeps: bool = True, forceReinstall: bool = False):
		self.upgrade = upgrade
		self.resolveDeps = resolveDeps
		self.forceReinstall = forceReinstall

	def clone(self, upgrade: typing.Optional[bool] = None, resolveDeps: typing.Optional[bool] = None, forceReinstall: typing.Optional[bool] = None):
		return __class__(upgrade=self.upgrade if upgrade is None else upgrade, resolveDeps=self.resolveDeps if resolveDeps is None else resolveDeps, forceReinstall=self.forceReinstall if forceReinstall is None else forceReinstall)


class PackagesInstaller:
	__slots__ = ("installDirs", "sourcesDir", "registry", "ignored")

	def __init__(self, registry: "IRegistry"):
		self.registry = registry
		self._reset()

	def _reset(self):
		self.installDirs = {}
		self.ignored = set()
		self.sourcesDir = None

	def __call__(self, prefs: ResolutionPrefs, names: typing.Collection[str]):
		self._reset()
		self.sourcesDir = TemporaryDirectory(prefix="install_", dir=Path("."))
		# self.sourcesDir = Path(".") / ("install_")

		self.downloadPackagesAndTheirDependencies(prefs, names)

		self.sourcesDir.cleanup()

	def downloadPackagesAndTheirDependencies(self, prefs: ResolutionPrefs, names: typing.Collection[str]):
		rr = ResolutionRound()
		rr.pkgs.toFetch.update({canonicalizedRequirement(el).name: 1 for el in names})
		ic(rr)

		while rr:
			rr = rr(prefs.clone(upgrade=False), self.installDirs, Path(self.sourcesDir.name), self.registry)
			ic(rr)

		rr.buildAndInstallWheel(self.installDirs)


class ResolutionSubRoundPipelineStage(IntEnum):
	notResolved = 0
	fetched = 1
	depsResolved = 2
	built = 3
	installed = 4


class ResolutionRoundSubRound(IntEnum):
	build = 0
	pkgs = 1


class ResolutionSubRound:
	__slots__ = ("idx", "resolved", "fetched", "toFetch", "ignored", "packageTypeName", "depsGetter", "moveToThis", "prefsPatch")

	def __init__(self, idx: ResolutionRoundSubRound, packageTypeName: str, depsGetter, moveToThis: bool, prefsPatch: dict):
		self.idx = idx
		self.packageTypeName = packageTypeName
		self.depsGetter = depsGetter
		self.moveToThis = moveToThis
		self.prefsPatch = prefsPatch
		self.toFetch = {}
		self.fetched = {}
		self.resolved = {}
		self.ignored = {}

	def __bool__(self) -> bool:
		return bool(self.toFetch)

	def __repr__(self):
		return self.__class__.__name__ + "<" + ", ".join(map(repr, (self.packageTypeName, len(self.resolved), len(self.toFetch), len(self.ignored)))) + ">"

	def fetch(self, installDirs, sourcesDir, registry):
		ic(self.packageTypeName, self.toFetch)
		buildDepsInstallDirs, ignored = clonePackagesRepos(sourcesDir, self.toFetch, registry)
		ic(self.packageTypeName, buildDepsInstallDirs, ignored)
		for ignoredPackage in ignored:
			if ignoredPackage.fetcher.type not in {Source.system}:
				raise NotImplementedError("Fetcher is not implemented yet")
		ignoredNames = {el.name: el for el in ignored}
		self.fetched.update(buildDepsInstallDirs)
		self.toFetch = {}
		self.ignored.update(ignoredNames)
		ic(self)

	def buildAndInstallWheel(self, installDirs):
		if self.resolved:
			print(styles.operationName("Installing") + " " + styles.entity(self.packageTypeName) + "s")
			for t in self.resolved:
				buildAndInstallWheel(installDirs[t])
		else:
			print(styles.success("No " + styles.entity(self.packageTypeName) + "s to install"))

	def isReInstallationNeeded(self, el, prefs: ResolutionPrefs):
		if el.marker:
			return False

		version = install.getInstalledPackageVersion(el.name)
		if version:
			print(styles.entity(self.packageTypeName) + " " + styles.varContent(el.name) + " " + styles.entity("version") + " installed: " + styles.varContent(str(version)))
			if not prefs.upgrade:
				print(styles.operationName("No upgrade") + ", may " + styles.operationName("skip") + " if suitable " + styles.entity("version") + " installed")
				if prefs.forceReinstall:
					print(styles.operationName("Forcing reinstallation..."), styles.varContent(el))
				else:					
					if list(el.specifier.filter((version,), prereleases=True)):
						print(styles.success("Suitable " + styles.entity("version") + " installed") + ", " + styles.operationName("skipping ") + str(styles.varContent(el)))
						return False
			else:
				print("`upgrade`==`True`, non-skipping", el)
		else:
			print(styles.entity(self.packageTypeName) + " " + styles.varContent(el.name) + " " + "not installed")

		return True

	def isAlreadyBeingProcessed(self, el) -> ResolutionSubRoundPipelineStage:
		for stage, collectionGetter in self.__class__._STAGE_TO_COLLECTION.items():
			isAlreadyFetched = collectionGetter(self).get(el, None)
			if isAlreadyFetched:
				return stage

		return ResolutionSubRoundPipelineStage.notResolved

	_STAGE_TO_COLLECTION = {
		# ResolutionSubRoundPipelineStage.notResolved: lambda self: self.toFetch,
		ResolutionSubRoundPipelineStage.fetched: lambda self: self.fetched,
		ResolutionSubRoundPipelineStage.depsResolved: lambda self: self.resolved,
	}

	def stageToCollection(self, stage: ResolutionSubRoundPipelineStage):
		return self.__class__._STAGE_TO_COLLECTION[stage](self)

	def appendNewDeps(self, prefs: ResolutionPrefs, srcList, otherSubRounds: typing.List["ResolutionSubRound"], successor: "ResolutionSubRound"):
		ic(self.packageTypeName, srcList)

		# ToDo: Markers are currently ignored
		for el in srcList:
			ic(el.name in self.ignored)
			if el.name in self.ignored:
				print(styles.operationName("Ignoring") + " " + styles.entity(self.packageTypeName) + ", must be system installed: " + styles.varContent(str(el)))
				continue

			ic(self.isReInstallationNeeded(el, prefs))
			if not self.isReInstallationNeeded(el, prefs):
				continue

			el = el.name

			for otherSubRound in otherSubRounds:
				ic(otherSubRound)
				otherRoundStage = otherSubRound.isAlreadyBeingProcessed(el)
				if otherRoundStage:
					if self.moveToThis:
						otherRoundCollection = otherSubRound.stageToCollection(otherRoundStage)
						thisRoundCollection = otherSubRound.stageToCollection(otherRoundStage)
						thisRoundCollection[el] = 1
						del otherRoundCollection[el]
					else:
						print(styles.success("Already") + " " + styles.operationName("scheduled") + " for " + styles.operationName(otherRoundStage.name) + " in " + styles.entity(otherSubRound.packageTypeName) + "s, skipping")
					continue

			currentRoundStage = self.isAlreadyBeingProcessed(el)
			if currentRoundStage:
				print(styles.success("Already") + " " + styles.success(currentRoundStage.name) + " in " + styles.entity(self.packageTypeName) + "s, will be processed in the next round, skipping")
				continue

			successor.toFetch[el] = 1


class ResolutionRound:
	__slots__ = ("subRounds",)

	def __init__(self):
		self.subRounds = {
			ResolutionRoundSubRound.build: ResolutionSubRound(ResolutionRoundSubRound.build, "build tool", lambda prefs, md: md.buildDeps, moveToThis=True, prefsPatch={"forceReinstall": False}),
			ResolutionRoundSubRound.pkgs: ResolutionSubRound(ResolutionRoundSubRound.build, "package", lambda prefs, md: md.deps if prefs.resolveDeps and md.deps else (), moveToThis=False, prefsPatch={}),
		}

	@property
	def build(self):
		return self.subRounds[ResolutionRoundSubRound.build]

	@property
	def pkgs(self):
		return self.subRounds[ResolutionRoundSubRound.pkgs]

	def __bool__(self) -> bool:
		#ic(tuple(self.build.toFetch), self.pkgs.toFetch)
		return bool(self.build) or bool(self.pkgs)

	def __repr__(self):
		return self.__class__.__name__ + "<" + repr(self.build) + ", " + repr(self.pkgs) + ">"

	def thisOtherSubRounds(self):
		subRoundsSet = set(self.subRounds)

		for thisSubRoundIdx in self.subRounds:
			thisSubRound = self.subRounds[thisSubRoundIdx]
			otherSubRounds = [self.subRounds[otherSubRoundIdx] for otherSubRoundIdx in (subRoundsSet - {thisSubRoundIdx})]

			yield (thisSubRound, otherSubRounds)

	def subroundSuccessorPrefs(self, prefs: ResolutionPrefs, successor: "ResolutionRound"):
		for thisSubRoundIdx in self.subRounds:
			thisSubRound = self.subRounds[thisSubRoundIdx]
			thisSubRoundPrefs = prefs.clone(**thisSubRound.prefsPatch)
			successorSubRound = successor.subRounds[thisSubRoundIdx]

			yield (thisSubRound, successorSubRound, thisSubRoundPrefs)

	def _resolveDeps(self, prefs: ResolutionPrefs, successor: "ResolutionRound"):
		for thisSubRound, otherSubRounds in self.thisOtherSubRounds():
			ic(thisSubRound, otherSubRounds)
			for name, installDir in thisSubRound.fetched.items():
				ic(name, name not in thisSubRound.ignored)
				if name not in thisSubRound.ignored:
					md = extractMetadata(installDir)

					for (subRoundForDepsExtr, successorSubRound, thisSubRoundPrefs) in self.subroundSuccessorPrefs(prefs, successor):
						deps = subRoundForDepsExtr.depsGetter(prefs, md)
						for dep in deps:
							unpinRequirement(dep)

						thisSubRound.appendNewDeps(thisSubRoundPrefs, deps, otherSubRounds, successor=successorSubRound)
						thisSubRound.resolved[name] = installDir

				successorSubRound.resolved.update(thisSubRound.resolved)

	def __call__(self, prefs: ResolutionPrefs, installDirs, sourcesDir: Path, registry):
		nextRound = ResolutionRound()

		print("self.build.fetch(installDirs, sourcesDir, registry)")
		self.build.fetch(installDirs, sourcesDir, registry)
		print("self.pkgs.fetch(installDirs, sourcesDir, registry)")
		self.pkgs.fetch(installDirs, sourcesDir, registry)

		print("self._resolveDeps(prefs, successor=nextRound)")
		self._resolveDeps(prefs, successor=nextRound)

		installDirs.update(self.build.fetched)
		installDirs.update(self.pkgs.fetched)

		return nextRound

	def buildAndInstallWheel(self, installDirs):
		self.build.buildAndInstallWheel(installDirs)
		self.pkgs.buildAndInstallWheel(installDirs)


def buildWheelUsingRemotePEP517(packageDir: Path, outDir: Path, pythonPath=()):
	r = pythonBuild.RemotePep517()
	stdinContents = r.serializeArgs(packageDir, outDir)
	res = standalonePEP517Cmd(_in=stdinContents, _env=cookPythonPathEnvDict(pythonPath))
	return r.processOutput(str(res))


def buildWheelUsingSetupPy(packageDir: Path, outDir: Path, pythonPath=()):
	wheelCmd("--dist-dir", outDir, _cwd=packageDir, _env=cookPythonPathEnvDict(pythonPath))

	from .utils.metadataExtractor import extractMetadata

	md = extractMetadata(packageDir)
	print("package name", md.name)

	wheelFiles = list(outDir.glob(md.name + "-*.whl"))
	if len(wheelFiles) > 1:
		raise RuntimeError("More than 1 wheels for given package name in the wheel dir", wheelFiles)

	return wheelFiles[0]


def buildWheel(packageDir: Path, outDir: Path, pythonPath=(), _useSetupPy: bool = False):
	if not _useSetupPy:
		return pythonBuild.buildWheelUsingPEP517(packageDir, outDir, pythonPath)

	return buildWheelUsingSetupPy(packageDir, outDir, pythonPath)


def buildWheelFromGHUri(wheelsDir: Path, uri: str, buildPythonPath=()):
	suffix = "_" + PurePath(uri).name
	wheel = None
	with TemporaryDirectory(prefix="", dir=Path("."), suffix=suffix) as packageDir:
		packageDir = Path(packageDir).absolute().resolve()
		fetchers[Source.git](uri, packageDir)
		wheel = buildWheel(packageDir, wheelsDir, buildPythonPath)
	return wheel


def buildAndInstallWheel(packageDir: Path, buildPythonPath=(), installPythonPath=(), _useSetupPy: bool = False, installBackend=None, installConfig=None):
	with TemporaryDirectory(prefix="wheels", dir=packageDir) as wheelsDir:
		wheelsDir = Path(wheelsDir).absolute().resolve()
		builtWheel = buildWheel(packageDir, wheelsDir, pythonPath=buildPythonPath, _useSetupPy=_useSetupPy)
		# sudo --preserve-env=PYTHONPATH

		if not installPythonPath:
			if installBackend is None:
				installBackend = install.REINSTALL_BACKEND
		else:
			installBackend = partial(install.pipCliReInstaller, pythonPath=installPythonPath)

		print(installBackend)
		installBackend((builtWheel,), config=installConfig)


def buildAndInstallWheelFromGitURI(uri: str, buildPythonPath=(), installBackend=None, installConfig=None):
	suffix = "_" + PurePath(uri).name
	with TemporaryDirectory(prefix="", dir=Path("."), suffix=suffix) as wheelsDir:
		wheelsDir = Path(wheelsDir).absolute().resolve()
		builtWheel = buildWheelFromGHUri(wheelsDir, uri, buildPythonPath)

		if installBackend is None:
			installBackend = install.REINSTALL_BACKEND

		installBackend((builtWheel,), config=installConfig)
