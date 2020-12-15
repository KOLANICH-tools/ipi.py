import typing
from pathlib import Path

from ..bootstrap.tiers import BootstrapTier
from . import sh

git = sh.Command("git").bake(_fg=True)
gitClone = git.bake("clone")
gitSparseCheckout = git.bake("sparse-checkout")
gitSparseCheckoutSet = gitSparseCheckout.bake("set")


def fetchUsingGit(uri: str, targetDir: Path, depth: int = 50, refSpec: typing.Optional[str] = None, subDir: typing.Optional[str] = None):
	additionalArgs = ["--filter=tree:0"]
	if depth and depth > 0:
		additionalArgs.extend(("--depth", depth))

	if refSpec:
		additionalArgs.extend(("--single-branch", "--branch", refSpec))

	if subDir:
		additionalArgs.extend(("--no-checkout", "--sparse"))

	res = gitClone(uri, targetDir, *additionalArgs)

	if subDir:
		gitSparseCheckoutSet(subDir, _cwd=targetDir)

	return res


tier = BootstrapTier.bootstrap
