import sys


class WithInBandBorders:
	__slots__ = ("pre", "post", "stream")

	def __init__(self, pre, post, stream=sys.stdout):
		self.pre = pre
		self.post = post
		self.stream = stream

	def __enter__(self):
		self.stream.flush()
		print(self.pre, file=self.stream)
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		print(self.post, file=self.stream)


class GitHubActionsGroup(WithInBandBorders):
	__slots__ = ()

	def __init__(self, message: str):
		super().__init__("##[group] " + message, "##[endgroup]")
