try:
	from icecream import ic

	ic.configureOutput(includeContext=True, contextAbsPath=False)
except ImportError:
	from pprint import pformat

	def ic(*args, **kwargs):
		print(pformat(args) + pformat(kwargs))
