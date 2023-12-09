import os
import random
from enum import Enum

import yaml

from aimarafone import RESOURCES_DIR

with open(os.path.join(RESOURCES_DIR, "names.yaml"), "r") as file:
    DICT_names = yaml.safe_load(file)


class Genre(Enum):
    """Enum representing player genre."""

    MASCULINE = "masculine"
    FEMININE = "feminine"


def pick_a_name(genre: Genre):
    return random.choice(DICT_names["italian"][genre.value])


if __name__ == "__main__":
    print(pick_a_name(Genre.MASCULINE))
