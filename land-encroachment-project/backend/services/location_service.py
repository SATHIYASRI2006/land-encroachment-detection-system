from __future__ import annotations


CHENNAI_LAT_RANGE = (12.95, 13.25)
CHENNAI_LNG_RANGE = (80.18, 80.31)


def is_valid_chennai_coordinate(lat: float, lng: float) -> bool:
    return (
        CHENNAI_LAT_RANGE[0] <= float(lat) <= CHENNAI_LAT_RANGE[1]
        and CHENNAI_LNG_RANGE[0] <= float(lng) <= CHENNAI_LNG_RANGE[1]
    )


def coordinate_validation_message() -> str:
    return (
        "Coordinates must be within the Chennai land monitoring bounds "
        f"({CHENNAI_LAT_RANGE[0]}-{CHENNAI_LAT_RANGE[1]} lat, "
        f"{CHENNAI_LNG_RANGE[0]}-{CHENNAI_LNG_RANGE[1]} lng)."
    )
