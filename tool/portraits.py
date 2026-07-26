from __future__ import annotations

from typing import Literal

from tool.backends import Emotion


Outfit = Literal["sleepwear", "casual", "uniform", "kimono"]
OUTFITS: tuple[Outfit, ...] = (
    "sleepwear",
    "casual",
    "uniform",
    "kimono",
)


PORTRAIT_BASE_LAYERS: dict[str, dict[Outfit, tuple[int, ...]]] = {
    "a": {
        "sleepwear": (1956, 1957),
        "casual": (1978, 1979),
        "uniform": (1952, 1953),
        "kimono": (1950, 1951),
    },
    "b": {
        "sleepwear": (1718,),
        "casual": (1717,),
        "uniform": (1716,),
        "kimono": (1715,),
    },
}

PORTRAIT_EXPRESSION_LAYERS: dict[str, dict[Emotion, tuple[int, ...]]] = {
    "a": {
        "平静": (1292,),
        "高兴": (1316,),
        "害羞": (1480, 1958),
        "生气": (1620,),
        "惊讶": (1368,),
        "着急": (1399,),
    },
    "b": {
        "平静": (1306,),
        "高兴": (1352,),
        "害羞": (1406, 1719),
        "生气": (1641,),
        "惊讶": (1505,),
        "着急": (1731,),
    },
}

PORTRAIT_HAIR_LAYERS: dict[str, dict[Outfit, int]] = {
    "a": {
        "sleepwear": 1959,
        "casual": 1959,
        "uniform": 1959,
        "kimono": 1273,
    },
    "b": {
        "sleepwear": 1261,
        "casual": 1261,
        "uniform": 1261,
        "kimono": 1261,
    },
}

ASSERTIVE_EMOTIONS: set[Emotion] = {"高兴", "生气"}


def layers_for(
    portrait: str,
    emotion: Emotion,
    outfit: Outfit = "kimono",
) -> list[int]:
    portrait = portrait if portrait in PORTRAIT_BASE_LAYERS else "b"
    outfit = outfit if outfit in OUTFITS else "kimono"
    base_options = PORTRAIT_BASE_LAYERS[portrait][outfit]
    base_index = (
        1
        if len(base_options) > 1 and emotion in ASSERTIVE_EMOTIONS
        else 0
    )
    expression_map = PORTRAIT_EXPRESSION_LAYERS[portrait]
    return [
        base_options[base_index],
        *expression_map.get(emotion, expression_map["平静"]),
        PORTRAIT_HAIR_LAYERS[portrait][outfit],
    ]


def default_layers(
    portrait: str,
    outfit: Outfit = "kimono",
) -> list[int]:
    return layers_for(portrait, "平静", outfit)
