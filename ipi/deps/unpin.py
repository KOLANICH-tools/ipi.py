try:
	from unpin.patcher import filterSpecifiers, TransformsConfig
except:
	from warnings import warn
	warn("install `unpin` in order remove only malicious pinnings")
	
	def unpinRequirement(req: "packaging.requirements.Requirement") -> None:
		from packaging.specifiers import SpecifierSet
		req.specifier = SpecifierSet("")
else:
	tcfg = TransformsConfig()

	def unpinRequirement(req: "packaging.requirements.Requirement") -> None:
		filterSpecifiers(req.specifier, tcfg)
