from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DATA_FILE = os.getenv("IKARIAM_DATA_FILE", "ikariam_world_slim.json")
MAX_SEARCH_RESULTS = int(os.getenv("IKARIAM_MAX_SEARCH_RESULTS", "200"))

TRADEGOOD = {
    1: "Uzum",
    2: "Mermer",
    3: "Kristal",
    4: "Sulfur",
}

WONDER = {
    1: "Ors / Hephaistos",
    2: "Hades",
    3: "Demeter",
    4: "Athena",
    5: "Hermes",
    6: "Ares",
    7: "Poseidon",
    8: "Rodos",
}


def normalize_for_search(value: Any) -> str:
    text = str(value or "").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[\"'`´“”‘’«»„‟‹›]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def coord_key(x: int, y: int) -> str:
    return f"{x}:{y}"


def normalize_world_island(x: int, y: int, row: List[Any]) -> Dict[str, Any]:
    tradegood = int(row[2] or 0)
    wonder = int(row[3] or 0)
    cities_count = int(row[7] or 0)

    return {
        "x": int(x),
        "y": int(y),
        "islandId": str(row[0] or ""),
        "islandName": str(row[1] or "Unknown"),
        "tradegood": tradegood,
        "tradegoodName": TRADEGOOD.get(tradegood, "Unknown"),
        "wonder": wonder,
        "wonderName": WONDER.get(wonder, "Unknown"),
        "citiesCount": cities_count,
        "isEmpty": cities_count == 0,
        "hasHelios": str(row[9] or "0") != "0",
        "raw": row,
    }


def flatten_strings(value: Any, out: Optional[List[str]] = None) -> List[str]:
    if out is None:
        out = []

    if value is None:
        return out
    if isinstance(value, str):
        if value.strip():
            out.append(value.strip())
        return out
    if isinstance(value, (int, float, bool)):
        out.append(str(value))
        return out
    if isinstance(value, list):
        for item in value:
            flatten_strings(item, out)
        return out
    if isinstance(value, dict):
        for v in value.values():
            flatten_strings(v, out)
        return out

    return out


def extract_world_islands(world_data: Any) -> List[Dict[str, Any]]:
    islands: List[Dict[str, Any]] = []
    if not world_data:
        return islands

    if isinstance(world_data, list):
        for x, col in enumerate(world_data):
            if col is None:
                continue
            if isinstance(col, list):
                for y, row in enumerate(col):
                    if isinstance(row, list) and len(row) >= 2:
                        islands.append(normalize_world_island(x, y, row))
            elif isinstance(col, dict):
                for y, row in col.items():
                    if isinstance(row, list) and len(row) >= 2:
                        islands.append(normalize_world_island(int(x), int(y), row))
    elif isinstance(world_data, dict):
        for x, col in world_data.items():
            if col is None:
                continue
            if isinstance(col, list):
                for y, row in enumerate(col):
                    if isinstance(row, list) and len(row) >= 2:
                        islands.append(normalize_world_island(int(x), y, row))
            elif isinstance(col, dict):
                for y, row in col.items():
                    if isinstance(row, list) and len(row) >= 2:
                        islands.append(normalize_world_island(int(x), int(y), row))

    return islands


def build_typed_haystacks(parsed: Dict[str, Any]) -> Dict[str, str]:
    player_fields = [
        parsed.get("possiblePlayerNames"),
        parsed.get("possibleCityNames"),
        parsed.get("citySlots"),
        parsed.get("rawHints"),
        parsed.get("pageTextSample"),
    ]
    alliance_fields = [
        parsed.get("possibleAllianceNames"),
        parsed.get("rawHints"),
        parsed.get("pageTextSample"),
    ]

    raw_player = " | ".join(flatten_strings(player_fields))
    raw_alliance = " | ".join(flatten_strings(alliance_fields))
    raw_all = " | ".join(
        flatten_strings(
            [
                parsed.get("citySlots"),
                parsed.get("rawHints"),
                parsed.get("possiblePlayerNames"),
                parsed.get("possibleCityNames"),
                parsed.get("possibleAllianceNames"),
                parsed.get("pageTextSample"),
            ]
        )
    )

    if not raw_all:
        raw_all = json.dumps(parsed, ensure_ascii=False)

    return {
        "player": normalize_for_search(raw_player or raw_all),
        "alliance": normalize_for_search(raw_alliance or raw_all),
        "all": normalize_for_search(raw_all),
    }


class DataStore:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.meta: Dict[str, Any] = {}
        self.islands_by_coord: Dict[str, Dict[str, Any]] = {}
        self.details_by_coord: Dict[str, Dict[str, Any]] = {}
        self.search_index: List[Dict[str, Any]] = []

    def load(self) -> None:
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        with self.data_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        world_data = (data.get("world") or {}).get("data")
        details_results = (data.get("details") or {}).get("results") or []

        self.meta = {
            "createdAt": data.get("createdAt"),
            "worldSummary": data.get("worldSummary"),
            "detailSummary": data.get("detailSummary"),
        }

        islands = extract_world_islands(world_data)
        self.islands_by_coord = {coord_key(i["x"], i["y"]): i for i in islands}

        details_map: Dict[str, Dict[str, Any]] = {}
        search_rows: List[Dict[str, Any]] = []

        for d in details_results:
            x = int(d.get("x"))
            y = int(d.get("y"))
            key = coord_key(x, y)
            parsed = d.get("parsed") or {}

            details_map[key] = {
                "x": x,
                "y": y,
                "islandId": d.get("islandId"),
                "islandName": d.get("islandName"),
                "tradegood": d.get("tradegood"),
                "wonder": d.get("wonder"),
                "islandType": d.get("islandType"),
                "resourceLevelMaybe": d.get("resourceLevelMaybe"),
                "citiesCount": d.get("citiesCount"),
                "heliosRaw": d.get("heliosRaw"),
                "parsed": parsed,
            }

            typed_haystacks = build_typed_haystacks(parsed)
            search_rows.append(
                {
                    "key": key,
                    "x": x,
                    "y": y,
                    "haystack_all": typed_haystacks["all"],
                    "haystack_player": typed_haystacks["player"],
                    "haystack_alliance": typed_haystacks["alliance"],
                }
            )

            if key not in self.islands_by_coord:
                row = d.get("rawWorldRow") or [
                    d.get("islandId"),
                    d.get("islandName"),
                    d.get("tradegood"),
                    d.get("wonder"),
                    0,
                    d.get("islandType"),
                    d.get("resourceLevelMaybe"),
                    d.get("citiesCount"),
                    0,
                    d.get("heliosRaw"),
                    0,
                    0,
                ]
                self.islands_by_coord[key] = normalize_world_island(x, y, row)

        self.details_by_coord = details_map
        self.search_index = search_rows


base_dir = Path(__file__).resolve().parents[2]
store = DataStore(base_dir / DATA_FILE)
store.load()

app = FastAPI(title="Ikariam API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "dataFile": str(store.data_path.name),
        "islands": len(store.islands_by_coord),
        "details": len(store.details_by_coord),
    }


@app.get("/api/meta")
def api_meta() -> Dict[str, Any]:
    islands = list(store.islands_by_coord.values())
    empty = sum(1 for i in islands if i.get("isEmpty"))
    return {
        **store.meta,
        "islands": len(islands),
        "emptyIslands": empty,
        "cityIslands": len(islands) - empty,
    }


@app.get("/api/islands/summary")
def islands_summary() -> Dict[str, Any]:
    items = [
        {
            "x": i["x"],
            "y": i["y"],
            "islandName": i["islandName"],
            "tradegood": i["tradegood"],
            "tradegoodName": i["tradegoodName"],
            "wonder": i["wonder"],
            "wonderName": i["wonderName"],
            "citiesCount": i["citiesCount"],
            "isEmpty": i["isEmpty"],
            "hasHelios": i["hasHelios"],
        }
        for i in store.islands_by_coord.values()
    ]
    return {"items": items, "count": len(items)}


@app.get("/api/island/{x}/{y}")
def island_detail(x: int, y: int) -> Dict[str, Any]:
    key = coord_key(x, y)
    island = store.islands_by_coord.get(key)
    if not island:
        raise HTTPException(status_code=404, detail="Island not found")

    detail = store.details_by_coord.get(key)
    return {"island": island, "detail": detail}


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=2),
    mode: str = Query("all", pattern="^(all|player|alliance)$"),
    limit: int = Query(100, ge=1, le=MAX_SEARCH_RESULTS),
) -> Dict[str, Any]:
    needle = normalize_for_search(q)
    if not needle:
        return {
            "query": q,
            "normalized": needle,
            "mode": mode,
            "count": 0,
            "items": [],
        }

    haystack_key = {
        "all": "haystack_all",
        "player": "haystack_player",
        "alliance": "haystack_alliance",
    }[mode]

    matched = []
    for row in store.search_index:
        if needle not in row[haystack_key]:
            continue

        key = row["key"]
        island = store.islands_by_coord.get(key)
        if not island:
            continue

        detail = store.details_by_coord.get(key) or {}
        snippet = (detail.get("parsed") or {}).get("pageTextSample") or ""

        matched.append(
            {
                "x": row["x"],
                "y": row["y"],
                "islandName": island.get("islandName"),
                "citiesCount": island.get("citiesCount"),
                "tradegood": island.get("tradegood"),
                "tradegoodName": island.get("tradegoodName"),
                "wonder": island.get("wonder"),
                "wonderName": island.get("wonderName"),
                "matchType": mode,
                "snippet": snippet[:220],
            }
        )

        if len(matched) >= limit:
            break

    return {
        "query": q,
        "normalized": needle,
        "mode": mode,
        "count": len(matched),
        "items": matched,
    }
