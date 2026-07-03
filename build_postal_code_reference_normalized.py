import pathlib
import re

import pandas as pd


BASE_DIR = pathlib.Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "Postal Codes" / "postal_code_reference.csv"
OUTPUT_PATH = BASE_DIR / "Postal Codes" / "postal_code_reference_normalized.csv"


PREFIX_RULES = {
    "SK": [
        ("Bratislava", "Bratislava"),
        ("Košice", "Košice"),
    ],
    "CZ": [
        ("Praha", "Praha"),
        ("Brno", "Brno"),
        ("Ostrava", "Ostrava"),
        ("Plzeň", "Plzeň"),
        ("Liberec", "Liberec"),
        ("Olomouc", "Olomouc"),
        ("Pardubice", "Pardubice"),
        ("Hradec Králové", "Hradec Králové"),
        ("České Budějovice", "České Budějovice"),
        ("Ústí nad Labem", "Ústí nad Labem"),
    ],
    "HU": [
        ("Budapest", "Budapest"),
        ("Debrecen", "Debrecen"),
        ("Szeged", "Szeged"),
        ("Miskolc", "Miskolc"),
        ("Pécs", "Pécs"),
        ("Győr", "Győr"),
    ],
}


def normalize_city(country_code, city_raw, geonames_places_count):
    city = str(city_raw).strip() if city_raw is not None else ""
    if not city:
        return pd.NA, 0.0, "missing_city", "No city/place name available"

    for prefix, normalized in PREFIX_RULES.get(country_code, []):
        if city == prefix:
            return (
                normalized,
                1.0,
                "exact_major_city",
                "GeoNames place name already equals normalized major city",
            )
        if city.startswith(prefix + "-") or city.startswith(prefix + " "):
            return (
                normalized,
                0.98,
                "major_city_prefix_rule",
                f"Postal district/place starts with {prefix}",
            )

    roman_prefix = re.match(r"^(.+?)\s+[IVXLCDM]+-.+$", city)
    if roman_prefix:
        return (
            roman_prefix.group(1).strip(),
            0.9,
            "roman_district_prefix_removed",
            "Removed Roman-numeral city district suffix",
        )

    roman_suffix = re.match(r"^.+-(.+?)\s+[IVXLCDM]+$", city)
    if roman_suffix:
        return (
            roman_suffix.group(1).strip(),
            0.9,
            "roman_district_suffix_removed",
            "Removed Roman-numeral city district suffix",
        )

    trailing_number = re.match(r"^(.+?)\s+\d+$", city)
    if trailing_number:
        base_city = trailing_number.group(1).strip()
        if len(base_city) >= 3:
            return (
                base_city,
                0.85,
                "trailing_number_removed",
                "Removed trailing postal-zone number",
            )

    try:
        n_places = int(geonames_places_count) if pd.notna(geonames_places_count) else 1
    except (TypeError, ValueError):
        n_places = 1

    if n_places > 1:
        return (
            city,
            0.75,
            "ambiguous_postal_code_kept_representative",
            "Postal code maps to multiple GeoNames places; representative place kept",
        )

    return city, 0.95, "unchanged_single_place", "Single GeoNames place kept as normalized city"


def main():
    ref = pd.read_csv(INPUT_PATH, dtype="string", keep_default_na=False)

    for column in ["latitude", "longitude", "geonames_places_count"]:
        if column in ref.columns:
            ref[column] = pd.to_numeric(ref[column], errors="coerce")

    annotations = ref.apply(
        lambda row: normalize_city(
            row["country_code"],
            row["city"],
            row["geonames_places_count"],
        ),
        axis=1,
    )

    ref["city_raw"] = ref["city"]
    ref[
        [
            "city_normalized",
            "city_normalization_confidence",
            "city_normalization_method",
            "city_normalization_note",
        ]
    ] = pd.DataFrame(annotations.tolist(), index=ref.index)

    output_columns = [
        "country_code",
        "postal_code_clean",
        "city_raw",
        "city_normalized",
        "city_normalization_confidence",
        "city_normalization_method",
        "city_normalization_note",
        "admin_region",
        "admin_district",
        "latitude",
        "longitude",
        "geonames_places_count",
        "geonames_place_names",
    ]
    ref = ref[[column for column in output_columns if column in ref.columns]]
    ref.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    print(f"saved: {OUTPUT_PATH}")
    print(f"rows: {len(ref)}")
    print("\nmethod counts:")
    print(ref["city_normalization_method"].value_counts().to_string())
    print("\nchanged examples:")
    changed = ref[ref["city_raw"] != ref["city_normalized"]]
    print(changed.head(30).to_string(index=False))
    print("\nconfidence distribution:")
    print(ref["city_normalization_confidence"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()

