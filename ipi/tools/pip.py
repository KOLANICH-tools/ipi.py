import typing
from warnings import warn

SchemeT = typing.Mapping[str, str]

try:
	import sysconfig
	from os import getuid

	import setuptools  # setuptools must be imported before distutils! And `pip` imports `distutils`
	from pip._internal.locations import get_scheme, get_src_prefix
	from pip._internal.utils.virtualenv import running_under_virtualenv
except ImportError:
	warn("needed API of `pip` are not available. Install it!")
	getScheme = None
	getPipScheme = None
else:

	def getScheme() -> SchemeT:
		sch = sysconfig.get_paths()
		sch.update(getPipScheme())
		return sch

	def getPipScheme(distName: str = "") -> SchemeT:
		isRoot = getuid() == 0 or running_under_virtualenv()
		sch = get_scheme(dist_name=distName, user=not isRoot, home=None, root=None, isolated=False, prefix=None)
		return {k: getattr(sch, k) for k in sch.__class__.__slots__}
