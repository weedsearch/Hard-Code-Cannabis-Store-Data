import reflex as rx
import json
import logging
from typing import TypedDict
from urllib.request import Request, urlopen


class Retailer(TypedDict):
    id: str
    name: str
    address: str
    town: str
    zip: str
    state: str
    phone: str
    designation: str
    priority: str
    website: str
    coordinates: list[str]


SOURCE_URL = "https://masscannabiscontrol.com/where-to-buy/"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ZmWpKNS238IXF-fZtr0d7-a9eGshs6ua3-MUnEFvQ3U/gviz/tq?tqx=out:json;responseHandler=paulCallBack"
EXPECTED_ROWS = 423


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _load_snapshot() -> list[Retailer]:
    try:
        request = Request(
            SHEET_URL,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json,text/plain,*/*",
            },
            method="GET",
        )
        with urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Public source returned no JSON object")
        payload = json.loads(text[start : end + 1])
        if payload.get("status") != "ok":
            raise ValueError("Public source response status is not ok")
        rows = payload["table"]["rows"]
        if not isinstance(rows, list) or len(rows) != EXPECTED_ROWS:
            raise ValueError(
                f"Public source must contain exactly {EXPECTED_ROWS} rows; received {len(rows)}"
            )
        records: list[Retailer] = []
        for row in rows:
            cells = row.get("c", [])
            values = [
                _text(cells[i].get("v"))
                if i < len(cells) and cells[i] is not None
                else ""
                for i in range(11)
            ]
            postal_code = values[4]
            if postal_code.isdigit():
                postal_code = postal_code.zfill(5)
            coordinates = json.loads(values[10]) if values[10] else []
            if not isinstance(coordinates, list):
                raise ValueError(f"Invalid coordinates for record {values[0]}")
            records.append(
                Retailer(
                    id=values[0],
                    name=values[1],
                    address=values[2],
                    town=values[3],
                    zip=postal_code,
                    state=values[5],
                    phone=values[6],
                    designation=values[7],
                    priority=values[8]
                    .removeprefix("Priority Status: ")
                    .strip(),
                    website=values[9],
                    coordinates=[_text(value) for value in coordinates],
                )
            )
        return records
    except Exception as e:
        logging.exception(f"Error: {e}")
        raise RuntimeError(
            f"Retailer directory startup failed: could not load the complete {EXPECTED_ROWS}-row public-source snapshot. {e}"
        ) from e


RETAILERS: list[Retailer] = _load_snapshot()
SNAPSHOT_COMPLETE: bool = len(RETAILERS) == EXPECTED_ROWS
