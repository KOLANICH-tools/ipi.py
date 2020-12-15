import typing

from distlib.database import DistributionPath

from ..utils import canonicalizePackageNameMulti
from .pip import SchemeT, getScheme


def genDistlibPath(scheme: typing.Optional[SchemeT] = None) -> typing.Iterable[str]:
	if scheme is None:
		scheme = getScheme()

	return tuple(scheme[k] for k in ("platlib", "platstdlib", "purelib"))


def genDistlibDistributionPath(scheme: typing.Optional[SchemeT] = None):
	return DistributionPath(genDistlibPath(scheme))


def getInstalledPackageDistribution(name: str):
	dp = genDistlibDistributionPath()
	dashName, underscoreName = canonicalizePackageNameMulti(name)

	if dashName != underscoreName:  # it may be any combination!
		dDist = dp.get_distribution(dashName)
		uDist = dp.get_distribution(underscoreName)

		if dDist and uDist:
			raise RuntimeError("Both underscore and dash dists are present, refuse to guess", dDist, uDist)

		return dDist if dDist else uDist
	else:
		return dp.get_distribution(dashName)
