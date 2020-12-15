from pathlib import Path

_appdirsConfigDict = {
	"appname": "ipi",
	"appauthor": "KOLANICH",
	"roaming": True,
}

try:
	import appdirs
except ImportError:
	try:
		import platformdirs
	except ImportError:
		settingsDirs = None
		settingsDir = None
		privateRegistriesDir = None
		reposRoot = None
	else:
		settingsDir = Path(platformdirs.user_state_dir(**_appdirsConfigDict))
else:
	settingsDirs = appdirs.AppDirs(multipath=False, **_appdirsConfigDict)
	settingsDir = Path(settingsDirs.user_state_dir)

if settingsDir is not None:
	privateRegistriesDir = settingsDir / "privateRegs"
	reposRoot = settingsDir / "tuf"
