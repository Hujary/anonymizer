from __future__ import annotations

from functools import lru_cache

from core import config
from validation.postcode import PostcodeValidator


@lru_cache(maxsize=1)
def get_postcode_validator() -> PostcodeValidator:
    model_path = config.get("postcode_ml_model_path", "models/plz_validator.pkl")
    reference_path = config.get("postcode_reference_path", "data_postal/postcodes_merged_unique.csv")
    unknown_postcode_malus = float(config.get("postcode_unknown_malus", 0.10))

    return PostcodeValidator.from_pickle(
        model_path=model_path,
        postcode_reference_path=reference_path,
        unknown_postcode_malus=unknown_postcode_malus,
    )