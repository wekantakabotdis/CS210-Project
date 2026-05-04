"""Build the Pokemon card pricing dataset from public TCGCSV endpoints."""

import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


GROUPS_URL = "https://tcgcsv.com/tcgplayer/3/groups"
GROUP_PRODUCTS_URL = "https://tcgcsv.com/tcgplayer/3/{group_id}/products"
GROUP_PRICES_URL = "https://tcgcsv.com/tcgplayer/3/{group_id}/prices"
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent / "data" / "pokemon_card_price_dataset.csv"
)
ENERGY_SYMBOL_PATTERN = re.compile(r"\[([A-Z]+)\]")


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "CS210-Project-Importer/1.0",
            "Accept": "application/json",
        }
    )
    return session


def fetch_json(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def extended_data_to_dict(entries: list[dict[str, Any]] | None) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for item in entries or []:
        key = item.get("name")
        value = item.get("value")
        if key:
            flattened[str(key)] = "" if value is None else str(value)
    return flattened


def parse_int(value: Any) -> float:
    if value in (None, ""):
        return float("nan")
    match = re.search(r"\d+", str(value))
    return float(match.group()) if match else float("nan")


def parse_card_number(number_value: str) -> tuple[float, float]:
    if not number_value:
        return float("nan"), float("nan")
    match = re.match(r"\s*(\d+)\s*/\s*(\d+)\s*$", number_value)
    if match:
        return float(match.group(1)), float(match.group(2))
    return parse_int(number_value), float("nan")


def count_attack_fields(card_data: dict[str, str]) -> tuple[int, float]:
    attack_values = [value for key, value in card_data.items() if key.startswith("Attack ")]
    if not attack_values:
        return 0, 0.0

    energy_lengths: list[float] = []
    for value in attack_values:
        symbols = ENERGY_SYMBOL_PATTERN.findall(value.strip())
        energy_lengths.append(float(sum(len(symbol) for symbol in symbols)))
    return len(attack_values), float(sum(energy_lengths) / len(energy_lengths))


def first_card_type(raw_value: str) -> str:
    if not raw_value:
        return "Unknown"
    return raw_value.split("/")[0].split(",")[0].strip() or "Unknown"


def looks_like_pokemon_card(card_data: dict[str, str]) -> bool:
    return bool(card_data.get("Number") and card_data.get("HP") and card_data.get("Card Type"))


def build_dataset(max_groups: int | None = None, pause_seconds: float = 0.12) -> pd.DataFrame:
    session = build_session()
    groups_payload = fetch_json(session, GROUPS_URL)
    groups = groups_payload["results"]
    selected_groups = groups[:max_groups] if max_groups else groups

    rows: list[dict[str, Any]] = []
    today = pd.Timestamp.today().normalize()

    for index, group in enumerate(selected_groups, start=1):
        group_id = group["groupId"]
        products = fetch_json(session, GROUP_PRODUCTS_URL.format(group_id=group_id))["results"]
        prices = fetch_json(session, GROUP_PRICES_URL.format(group_id=group_id))["results"]

        products_by_id = {product["productId"]: product for product in products}
        set_release_date = pd.to_datetime(group.get("publishedOn"), errors="coerce", utc=True)
        if pd.notna(set_release_date):
            set_release_date = set_release_date.tz_localize(None)

        print(
            f"Processed group {index}/{len(selected_groups)}: "
            f"{group.get('name', 'Unknown')} ({len(products)} products)"
        )

        for price_row in prices:
            market_price = price_row.get("marketPrice")
            if market_price is None or float(market_price) <= 0:
                continue

            product = products_by_id.get(price_row["productId"])
            if not product:
                continue

            card_data = extended_data_to_dict(product.get("extendedData"))
            if not looks_like_pokemon_card(card_data):
                continue

            card_number_numeric, set_total = parse_card_number(card_data.get("Number", ""))
            attack_count, avg_attack_cost_length = count_attack_fields(card_data)
            weakness_count = sum(
                1 for key in card_data if key.startswith("Weakness")
            ) or int(bool(card_data.get("Weakness")))
            resistance_count = sum(
                1 for key in card_data if key.startswith("Resistance")
            ) or int(bool(card_data.get("Resistance")))
            retreat_cost_count = parse_int(
                card_data.get("RetreatCost") or card_data.get("Retreat Cost")
            )

            rows.append(
                {
                    "card_id": product["productId"],
                    "card_name": product.get("name"),
                    "set_id": group_id,
                    "set_name": group.get("name"),
                    "set_release_date": set_release_date,
                    "market_price_usd": float(market_price),
                    "finish_type": price_row.get("subTypeName") or "Unknown",
                    "rarity": card_data.get("Rarity") or "Unknown",
                    "hp": parse_int(card_data.get("HP")),
                    "primary_type": first_card_type(card_data.get("Card Type", "")),
                    "primary_subtype": card_data.get("Stage") or "Unknown",
                    "retreat_cost_count": retreat_cost_count,
                    "weakness_count": float(weakness_count),
                    "resistance_count": float(resistance_count),
                    "attack_count": attack_count,
                    "avg_attack_cost_length": avg_attack_cost_length,
                    "set_total": set_total,
                    "age_days": float((today - set_release_date.normalize()).days)
                    if pd.notna(set_release_date)
                    else float("nan"),
                    "card_number_numeric": card_number_numeric,
                    "is_secret_rare": float(
                        pd.notna(card_number_numeric)
                        and pd.notna(set_total)
                        and card_number_numeric > set_total
                    ),
                    "product_url": product.get("url"),
                }
            )

        time.sleep(pause_seconds)

    if not rows:
        raise ValueError("No Pokemon card rows were extracted from TCGCSV.")

    dataset = pd.DataFrame(rows).sort_values(
        ["set_release_date", "set_name", "card_name", "finish_type"],
        na_position="last",
    )
    dataset = dataset.reset_index(drop=True)
    return dataset


def save_dataset(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    max_groups: int | None = None,
    pause_seconds: float = 0.12,
) -> pd.DataFrame:
    dataset = build_dataset(max_groups=max_groups, pause_seconds=pause_seconds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)
    return dataset


if __name__ == "__main__":
    dataset = save_dataset()
    print(f"\nSaved {len(dataset):,} rows to {DEFAULT_OUTPUT_PATH}")
    print(dataset.head().to_string(index=False))
