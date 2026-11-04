"""StarCraft II games as data: the `.salsa` file format, which `SPEC.md` describes.

`write_salsa_file` plays a replay back as each of its players, through NachOS, and writes the game to a `.salsa` file.
"""

from sc2salsa.__about__ import __version__
from sc2salsa._schema import FORMAT_VERSION
from sc2salsa._writer import write_salsa_file

__all__ = ["FORMAT_VERSION", "__version__", "write_salsa_file"]
