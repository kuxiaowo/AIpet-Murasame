from __future__ import annotations

from tool.backends import Emotion


PORTRAIT_LAYERS: dict[str, dict[Emotion, list[int]]] = {
    "a": {
        "平静": [1950, 1292],
        "高兴": [1950, 1316],
        "害羞": [1950, 1480, 1958],
        "生气": [1950, 1620],
        "惊讶": [1950, 1368],
        "着急": [1950, 1399],
    },
    "b": {
        "平静": [1715, 1306],
        "高兴": [1715, 1352],
        "害羞": [1715, 1406, 1719],
        "生气": [1715, 1641],
        "惊讶": [1715, 1505],
        "着急": [1715, 1731],
    },
}


def layers_for(portrait: str, emotion: Emotion) -> list[int]:
    portrait_map = PORTRAIT_LAYERS.get(portrait, PORTRAIT_LAYERS["b"])
    return list(portrait_map.get(emotion, portrait_map["平静"]))


def default_layers(portrait: str) -> list[int]:
    return layers_for(portrait, "平静")
