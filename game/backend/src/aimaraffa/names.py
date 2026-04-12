"""Random Italian name generator used for bot player names."""

import os
import random
from enum import Enum

import yaml


_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")

with open(os.path.join(_RESOURCES_DIR, "names.yaml"), encoding="utf-8") as _f:
    _NAMES: dict = yaml.safe_load(_f)


class Genre(Enum):
    """Gender used to pick a matching Italian name."""

    MASCULINE = "masculine"
    FEMININE = "feminine"


def pick_a_name(genre: Genre) -> str:
    """Return a random Italian first name for the given genre."""
    return random.choice(_NAMES["italian"][genre.value])


def random_bot_name() -> str:
    """Return a grandparent-style bot name like 'Nonno Gino' or 'Nonna Rosa'."""
    genre = random.choice(list(Genre))
    prefix = "Nonno" if genre == Genre.MASCULINE else "Nonna"
    return f"{prefix} {pick_a_name(genre)}"
