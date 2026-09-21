import reflex as rx
from pathlib import Path
from typing import TypedDict
import json
import logging


class Flower(TypedDict):
    name: str
    thc: str
    price: str
    weight: str
    store: str
    source_url: str
    provider: str


def snapshot_path() -> Path:
    return rx.get_upload_dir() / "flower_snapshot.json"


def load_flowers() -> dict:
    try:
        path = snapshot_path()
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        if data.get("version") != 1 or not data.get("complete"):
            return {}
        return data
    except Exception as e:
        logging.exception(f"Error: {e}")
        return {}
