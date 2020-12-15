import re
import sys
from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory

from ..defaultPetnames import builtInRegistries
from ..deps.git import fetchUsingGit
from ..pipelines import buildAndInstallWheel, clonePackagesRepos
from ..tools.install import setupPyInstall
from ..tools.setup_py import eggInfoCmd
from ..utils.WithInBandBorders import GitHubActionsGroup
from ..utils.WithPythonPath import cookPythonPathEnvDict
from .utils import bootstrapBySequence


def bootstrapPythonPackaging():
	with TemporaryDirectory(prefix="bootstrap_", dir=Path(".")) as tempDir:
		tempDir = Path(tempDir).absolute().resolve()
		bootstrapSetuptoolsAndPip(tempDir)
		bootstrapTheRestPackagingEcosystem(tempDir)
		finalInstallSetuptools(tempDir / "setuptools")
		bootstrapHatchling(tempDir)


def cloneSetuptoolsAndWheel(targetDir: Path):
	essentialPackages = {
		"setuptools": 50,
		"wheel": 50,
	}
	with GitHubActionsGroup("Bootstrapping packaging: Cloning essential packages: " + ", ".join(essentialPackages)):
		clonedDirs, ignores = clonePackagesRepos(targetDir, essentialPackages, builtInRegistries)
		assert not ignores, ignores
	return clonedDirs["setuptools"], clonedDirs["wheel"]


def removePreinstalledSetuptools():
	"""sudo rm -rf /usr/lib/python3/dist-packages/setuptools;"""
	"""sudo rm -rf /usr/lib/python3/dist-packages/setuptools-*.egg-info;"""


def eggInfo(targetDir: Path, name: str):
	with GitHubActionsGroup("Bootstrapping packaging: " + name + " egg_info"):
		eggInfoCmd(_cwd=targetDir)


def bootstrapSetuptoolsAndPip(tempDir: Path):
	removePreinstalledSetuptools()
	setuptoolsDir, wheelDir = cloneSetuptoolsAndWheel(tempDir)
	eggInfo(setuptoolsDir, "setuptools")
	roughWheel(wheelDir, setuptoolsDir)

	pipDir = tempDir / "pip"
	installPip(pipDir, setuptoolsDir)
	finalWheel(wheelDir, setuptoolsDir)
	installSetuptools(setuptoolsDir)


def fixSetupCfgForWheel(targetDir: Path):
	f = targetDir / "setup.cfg"
	res = re.subn("^install_requires.+$", "", f.read_text(), flags=re.MULTILINE)[0]
	f.write_text(res)


def roughWheel(targetDir: Path, setuptoolsDir: Path):
	with GitHubActionsGroup("Bootstrapping packaging: Rough install wheel"):
		fixSetupCfgForWheel(targetDir)
		# sudo --preserve-env=PYTHONPATH
		setupPyInstall(targetDir, (setuptoolsDir, targetDir / "src"))
		# sudo chown -R `id -un`:`id -gn` .;


def installPip(targetDir: Path, setuptoolsDir: Path):
	with GitHubActionsGroup("Bootstrapping packaging: Install pip"):
		fetchUsingGit(builtInRegistries.lookup("pip").pkg.fetcher.repo, targetDir)

		buildAndInstallWheel(targetDir, buildPythonPath=(setuptoolsDir,), installPythonPath=(targetDir / "src",), _useSetupPy=True)
		# sudo chown -R `id -un`:`id -gn` .;

		# sudo rm -rf ./pip;


def finalWheel(targetDir: Path, setuptoolsDir: Path):
	with GitHubActionsGroup("Bootstrapping packaging: Final install wheel"):
		buildAndInstallWheel(targetDir, buildPythonPath=(setuptoolsDir,), _useSetupPy=True)


def installSetuptools(targetDir: Path):
	with GitHubActionsGroup("Bootstrapping packaging: Install setuptools"):
		buildAndInstallWheel(targetDir, _useSetupPy=True)


def bootstrapBySchedule(tempDir: Path, schedule):
	with GitHubActionsGroup("Cloning the rest of packages: " + ", ".join(schedule)):
		clonedDirs, ignores = clonePackagesRepos(tempDir, schedule, builtInRegistries)
		assert not ignores, ignores

	bootstrapBySequence(clonedDirs, schedule.items())


def bootstrapTheRestPackagingEcosystem(tempDir: Path):
	restOfEssentialPackages = ("tomli", "pyparsing", "flit_core", "pyproject-hooks", "packaging", "build", "typing_extensions", "setuptools_scm")
	with GitHubActionsGroup("Cloning the rest of packages: " + ", ".join(restOfEssentialPackages)):
		clonedDirs, ignores = clonePackagesRepos(tempDir, restOfEssentialPackages, builtInRegistries)
		assert not ignores, ignores

	pphDir = clonedDirs["pyproject-hooks"] / "src"

	bootstrapBySequence(
		clonedDirs,
		(
			("tomli", (clonedDirs["tomli"] / "src", pphDir, "flit_core")),
			("pyparsing", (pphDir, "flit_core", "packaging")),
			("packaging", (pphDir, "flit_core")),
			("flit_core", ("packaging", pphDir, "tomli")),
			("pyproject-hooks", (pphDir, "packaging", "flit_core", "tomli")),  # importlib_metadata;python_version<'3.8', zipp;python_version<'3.8

			("setuptools_scm", ("typing_extensions",)),
			("typing_extensions", ("flit_core",)),
			("build", ("packaging", "pyproject-hooks", "tomli")),
		),
	)


def bootstrapHatchling(tempDir: Path):
	installSchedule = OrderedDict(
		(
			("pathspec", ()),
			("editables", ()),
		)
	)

	pluggyDeps = []
	hatchlingDeps = [
		"pathspec",
		"pluggy",
	]

	if tuple(sys.version_info)[:3] < (3, 8):
		installSchedule.update((("zipp", ()), ("importlib-metadata", ("zipp",))))
		pluggyDeps.append("importlib-metadata")
		hatchlingDeps.append("importlib-metadata")

	installSchedule.update((("pluggy", tuple(pluggyDeps)), ("hatchling", tuple(hatchlingDeps))))
	bootstrapBySchedule(tempDir, installSchedule)


def finalInstallSetuptools(targetDir):
	with GitHubActionsGroup("Installing This time setuptools with correct metadata"):
		# rm -rf ./setuptools.egg-info ./build ./dist
		buildAndInstallWheel(targetDir)
