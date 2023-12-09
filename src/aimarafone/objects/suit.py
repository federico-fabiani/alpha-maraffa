from enum import Enum


class Suit(Enum):
    """Enum representing card suits."""

    BASTONI = "Bastoni"
    DENARA = "Denara"
    SPADE = "Spade"
    COPPE = "Coppe"


if __name__ == "__main__":
    for suit in Suit:
        print(suit.name, suit.value)
