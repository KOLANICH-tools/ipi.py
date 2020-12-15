try:
	from RichConsole import groups

	class styles:
		success = groups.Fore.lightgreenEx
		operationName = groups.Fore.yellow
		entity = groups.Fore.lightblueEx
		varContent = groups.Fore.lightmagentaEx
		error = groups.Fore.lightredEx

except BaseException:

	class styles:
		error = varContent = entity = operationName = success = lambda x: x
