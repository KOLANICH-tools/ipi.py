import sys
import typing
from pathlib import Path
from warnings import warn

from ..deps import sh
from ..utils.WithPythonPath import WithPythonPath, cookPythonPathEnvDict
from .pip import getScheme
from .python import python
from .setup_py import setupPy

setupPyInstallCmd = setupPy.bake("install")

try:
	from packaging.version import Version
except ImportError:
	Version = None

try:
	from .distlib import getInstalledPackageDistribution
except ImportError:
	warn("`distlib` is not available, install it")

	import importlib.metadata

	def getInstalledPackageDistribution(name: str):
		try:
			return importlib.metadata.distribution(name)
		except importlib.metadata.PackageNotFoundError:
			return None


def getInstalledPackageVersion(name: str) -> typing.Optional[Version]:
	pkg = getInstalledPackageDistribution(name)
	if pkg is not None:
		return Version(pkg.version)

	return None


def setupPyInstall(targetDir: Path, pythonPath=()):
	"""Most likely you don't need it!"""
	return setupPyInstallCmd(_cwd=targetDir, _env=cookPythonPathEnvDict(pythonPath))


class Installer:
	__slots__ = ()

	def __call__(self, wheels: typing.Iterable[Path], config):
		raise NotImplementedError


class UnInstaller:
	__slots__ = ()

	def __call__(self, packageNames: typing.Iterable[str]):
		raise NotImplementedError


class ReInstaller(Installer):
	__slots__ = ("installer", "uninstaller")

	def __init__(self, installer: Installer, uninstaller: UnInstaller = None):
		self.installer = installer
		self.uninstaller = uninstaller

	def getInstalledVersion(self, packageName: str) -> Version:
		return getInstalledPackageVersion(packageName)

	def install(self, wheels: typing.Iterable[Path], config, **kwargs):
		return self.installer(wheels, config, **kwargs)

	def uninstall(self, packageNames: typing.Iterable[str], **kwargs):
		return self.uninstaller(packageNames, **kwargs)

	def extractPackageName(self, wheel: Path):
		try:
			from installer.sources import WheelFile
		except ImportError:
			from distlib.wheel import Wheel

			w = Wheel(wheel)
			return w.name
		else:
			import zipfile

			with zipfile.ZipFile(wheel) as z:
				w = WheelFile(z)
				return w.distribution

	def __call__(self, wheels: typing.Iterable[Path], config, **kwargs):
		toUninstall = []
		for w in wheels:
			packageName = self.extractPackageName(w)
			v = self.getInstalledVersion(packageName)
			if v:
				toUninstall.append(packageName)

		self.uninstall(toUninstall)
		self.install(wheels, config, **kwargs)


class InstallerLikeReinstaller(ReInstaller):
	__slots__ = ()

	def __call__(self, wheels: typing.Iterable[Path], config, **kwargs):
		self.install(wheels, config, **kwargs)


pip = python.bake("-m", "pip").bake(_fg=True)
_ignoreRootWarningArg = "--root-user-action=ignore"
pipInstallUpgradeCmd = pip.bake("install", _ignoreRootWarningArg, "--upgrade", "--force-reinstall", "--pre", "--disable-pip-version-check", "--no-build-isolation", "--ignore-installed", "--no-deps", "--no-index")
pipUnunstallCmd = pip.bake("uninstall", _ignoreRootWarningArg)


class PipCLIInstaller(Installer):
	__slots__ = ()

	def __call__(self, wheels: typing.Iterable[Path], config=None, pythonPath=()):
		print(wheels, config, pythonPath)
		if wheels:
			pipInstallUpgradeCmd(*wheels, _env=cookPythonPathEnvDict(pythonPath))


class PipCLIUnInstaller(Installer):
	__slots__ = ()

	def __call__(self, packageNames: typing.Iterable[str], pythonPath=()):
		print(packageNames, pythonPath)
		if packageNames:
			pipUnunstallCmd(*packageNames, _env=cookPythonPathEnvDict(pythonPath))


pipCliReInstaller = InstallerLikeReinstaller(PipCLIInstaller(), PipCLIUnInstaller())
REINSTALL_BACKEND = pipCliReInstaller


if getScheme:
	try:
		from installer import install
		from installer.destinations import SchemeDictionaryDestination
		from installer.sources import WheelFile
	except ImportError:
		warn("`installer` is not available. Install it!")
		installerInstaller = None
	else:

		try:
			import uninstaller
		except ImportError:
			warn("`uninstaller` is not available. Install it!")
			uninstallerUnInstaller = None
		else:

			class UnInstallerUnInstaller(Installer):
				__slots__ = ("pU", "iU")

				def __init__(self):
					root: str = None  # override package search root
					base: str = None  # override base path (aka prefix)
					scheme = getScheme()
					self.pU = uninstaller.Uninstaller(
						root=root,
						base=base,
						scheme=scheme,
						whl_scheme="purelib",
					)
					self.iU = uninstaller.Uninstaller(
						root=root,
						base=base,
						scheme=scheme,
						whl_scheme="platlib",
					)

				def __call__(self, packageNames: typing.Iterable[str]):
					for package in packageNames:
						pm = {}
						u = self.pU if pm.get("Root-is-Purelib", True) else self.iU
						u.uninstall(
							package,
							verbose=True,
						)

			uninstallerUnInstaller = UnInstallerUnInstaller()

		class InstallerInstaller(Installer):
			__slots__ = ()

			def __call__(self, wheels: typing.Iterable[Path], config=None):
				if config is None:
					config = {}

				dst = SchemeDictionaryDestination(
					getScheme(),
					interpreter=sys.executable,
					script_kind="posix",
					destdir=config.get("destDir", None),
				)
				for wheel in wheels:
					with WheelFile.open(wheel) as whl:
						install(whl, dst, config.get("installAdditionalMetadata", {}))

		installerReInstaller = ReInstaller(InstallerInstaller(), uninstallerUnInstaller if uninstallerUnInstaller is not None else pipCliReInstaller.uninstaller)
		REINSTALL_BACKEND = installerReInstaller  # ToDO: handle uninstallation and reinstallation
