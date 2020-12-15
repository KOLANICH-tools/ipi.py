import typing
from pathlib import Path
from warnings import warn

from ..bootstrap.tiers import BootstrapTier
from . import sh

hg = sh.Command("hg").bake(_fg=True)
hgClone = hg.bake("clone", "--rev", "default")


def fetchUsingMercurial(uri: str, targetDir: Path, depth: int = 50, refSpec: typing.Optional[str] = None):
	warn("depth is not supported for hg, see https://www.mercurial-scm.org/wiki/ShallowClone")
	return hgClone(uri, targetDir)


tier = BootstrapTier.bootstrap
