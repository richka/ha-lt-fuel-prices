"""Translation files must stay in sync and cover all entity names."""

from __future__ import annotations

import json
from pathlib import Path

TRANSLATIONS = (
    Path(__file__).parents[1]
    / "custom_components"
    / "lt_fuel_prices"
    / "translations"
)


def _load(language: str) -> dict:
    return json.loads(
        (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
    )


def test_translation_files_match() -> None:
    """English and Lithuanian files expose the same keys."""
    en = _load("en")
    lt = _load("lt")

    assert en["entity"].keys() == lt["entity"].keys()
    assert en["entity"]["sensor"].keys() == lt["entity"]["sensor"].keys()
    assert (
        en["entity"]["binary_sensor"].keys()
        == lt["entity"]["binary_sensor"].keys()
    )
    assert en["config"]["step"].keys() == lt["config"]["step"].keys()
    assert en["config"]["error"].keys() == lt["config"]["error"].keys()
    assert en["config"]["abort"].keys() == lt["config"]["abort"].keys()
    assert en["options"]["step"].keys() == lt["options"]["step"].keys()


def test_entity_names_are_translated() -> None:
    """Every entity translation key has a non-empty name."""
    for language in ("en", "lt"):
        data = _load(language)
        for platform in ("sensor", "binary_sensor"):
            for key, value in data["entity"][platform].items():
                assert value.get("name"), f"{language}: {platform}.{key}"
