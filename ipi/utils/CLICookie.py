import secrets
import typing
from string import ascii_lowercase, ascii_uppercase, digits

__all__ = ("CLICookie",)


def genCookie(length: int) -> str:
	return "".join(secrets.choice("".join((ascii_lowercase, ascii_uppercase, digits))) for _ in range(length))


class CLICookie:
	"""Helps you to separate your output from output of something else within the same process via in-band signalling."""

	__slots__ = ("start", "end")

	LENGTH = 32

	def __init__(self, start: str = None, end: str = None):
		if start is None:
			start = genCookie(self.__class__.LENGTH)

		self.start = start

		if end is None:
			end = genCookie(self.__class__.LENGTH)

		self.end = end

	def wrap(self, data: str):
		return "".join((self.start[::-1], data, self.end[::-1]))

	def toSerializeable(self):
		return [self.start, self.end]

	@classmethod
	def deserialize(cls, serialized: typing.Any):
		return cls(*serialized)

	def unwrap(self, data: str):
		targetStarts = data.find(self.start[::-1])
		preCookie, postCookie = "", ""

		if targetStarts > -1:
			preCookie = data[:targetStarts]

			data = data[targetStarts + self.__class__.LENGTH :]

		targetEnds = data.find(self.end[::-1])

		if targetEnds > -1:
			postCookie = data[targetEnds + self.__class__.LENGTH :]

			data = data[:targetEnds]

		return data, preCookie, postCookie
