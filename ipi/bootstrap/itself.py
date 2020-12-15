import typing
from pathlib import Path

from ..registries import initRegistries


def getCurrentGitSdistPyprojectToml() -> typing.Optional[Path]:
	rootDir = Path(__file__).resolve().absolute().parent.parent.parent
	gitDir = rootDir / ".git"
	pyprojectToml = rootDir / "pyproject.toml"
	if (gitDir.is_dir() or gitDir.is_file()) and pyprojectToml.is_file():
		return pyprojectToml

	return None


def bootstrapItself():
	from importlib import reload

	from .. import pipelines
	from ..tools import install

	gipv = install.getInstalledPackageVersion

	def reloadInstaller():
		nonlocal gipv

		reload(install)
		gipv = install.getInstalledPackageVersion
		reloadPipelines()

	ppToml = getCurrentGitSdistPyprojectToml()
	if not ppToml:
		raise RuntimeError("`bootstrap.self` must be called from a clone of git repo of ipi")

	regs = initRegistries()

	i = None  # type: pipelines.PackagesInstaller
	prefs = None  # type: pipelines.ResolutionPrefs

	def initInstaller():
		nonlocal i, prefs
		i = pipelines.PackagesInstaller(regs)
		prefs = pipelines.ResolutionPrefs(upgrade=True)

	initInstaller()

	def reloadPipelines():
		nonlocal i
		reload(pipelines)
		initInstaller()

	if not gipv("distlib"):
		i(prefs, ["distlib"])
		from ..tools import distlib

		reload(distlib)
		reloadInstaller()

	if not gipv("peval"):
		i(prefs, ["peval"])
		from ..utils import metadataExtractor

		reload(metadataExtractor)
		reloadPipelines()

	if not gipv("installer"):
		i(prefs, ["installer"])
		reloadInstaller()

	if not gipv("uninstaller"):
		i(prefs, ["uninstaller"])
		reloadInstaller()

	if not gipv("plumbum"):
		i(prefs, ["plumbum"])

	richConsoleInstalled = gipv("RichConsole")

	def reloadStyles():
		from ..utils import styles

		reload(styles)
		reloadPipelines()

	if not gipv("colorama"):
		i(prefs, ["colorama"])
		if richConsoleInstalled:
			import RichConsole

			reload(RichConsole)
			reloadStyles()

	if not richConsoleInstalled:
		i(prefs, ["RichConsole"])
		reloadStyles()

	i(prefs, ["ipi"])
