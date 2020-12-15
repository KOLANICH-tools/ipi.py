from enum import IntEnum

__all__ = ("BootstrapTier",)


class BootstrapTier(IntEnum):
	"""Bootstrap tiers"""

	bootstrap = 0
	bare = 1
	full = 0xFE


BootstrapTier.bootstrap.__doc__ = "Works on bare Python interpreter, requires no dependencies, but useful only for self-bootstrap."
BootstrapTier.bare.__doc__ = "Very limited, but works on bare Python interpreter. Requires no dependencies."
BootstrapTier.full.__doc__ = "Fully-functional, may require dependencies."
