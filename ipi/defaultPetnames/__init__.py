import typing
from pathlib import Path

"""The sources of packages are needed for ipi to be able to bootstrap itself lay in this dir."""

from ..registries import CompoundRegistry

thisDir = Path(__file__).parent

builtInRegistries = CompoundRegistry.fromCSVDir("builtin", thisDir, nameGen=lambda regF: ":builtin:" + regF.stem)
