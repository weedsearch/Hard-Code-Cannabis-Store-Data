import reflex as rx
import logging
from urllib.parse import urlsplit
from app.flower_data import Flower, load_flowers


class FlowerState(rx.State):
    rows: list[Flower] = []
    captured_at: str = ""
    coverage: dict[str, int] = {}
    loaded: bool = False
    query: str = ""
    store: str = ""
    sort_column: str = "name"
    descending: bool = False
    page: int = 1

    @rx.event
    def load_snapshot(self):
        data = load_flowers()
        self.loaded = False
        self.rows = []
        if not data:
            return
        try:
            rows = []
            for item in data.get("rows", []):
                row = {
                    k: str(item.get(k) or "") for k in Flower.__annotations__
                }
                p = urlsplit(row["source_url"])
                if (
                    p.scheme not in ("http", "https")
                    or not p.hostname
                    or p.username
                    or p.password
                ):
                    row["source_url"] = ""
                rows.append(row)
            self.rows = rows
            self.captured_at = str(data["captured_at"])
            self.coverage = {
                str(k): int(v) for k, v in data["coverage"].items()
            }
            self.loaded = True
            self.page = 1
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.rows = []

    @rx.var
    def coverage_label(self) -> str:
        c = self.coverage
        return f"{c.get('retailers', 0)} retailer records · {c.get('parsed_retailers', 0)} with flower · {c.get('omitted_retailers', 0)} omitted · {c.get('sources', 0)} sources checked · {c.get('listings', 0)} listings"

    @rx.var
    def coverage_details(self) -> list[str]:
        return [
            f"{k.replace('_', ' ')}: {v}"
            for k, v in sorted(self.coverage.items())
            if k.startswith(("sources_", "retailers_"))
        ]

    @rx.var
    def stores(self) -> list[str]:
        return sorted({r["store"] for r in self.rows})

    @rx.var
    def filtered(self) -> list[Flower]:
        terms = self.query.casefold().split()
        rows = [
            r
            for r in self.rows
            if (not self.store or r["store"] == self.store)
            and all(t in " ".join(r.values()).casefold() for t in terms)
        ]
        return sorted(
            rows,
            key=lambda r: (
                r[self.sort_column].casefold(),
                r["store"],
                r["name"],
                r["weight"],
                r["price"],
            ),
            reverse=self.descending,
        )

    @rx.var
    def count(self) -> int:
        return len(self.filtered)

    @rx.var
    def pages(self) -> int:
        return max(1, (self.count + 24) // 25)

    @rx.var
    def visible(self) -> list[Flower]:
        return self.filtered[(self.page - 1) * 25 : self.page * 25]

    @rx.var
    def range_label(self) -> str:
        if not self.count:
            return "0 results"
        return f"{(self.page - 1) * 25 + 1}–{min(self.page * 25, self.count)} of {self.count} results"

    @rx.event
    def search(self, value: str):
        self.query = value
        self.page = 1

    @rx.event
    def filter_store(self, value: str):
        self.store = value
        self.page = 1

    @rx.event
    def sort_by(self, column: str):
        if column not in ("name", "store"):
            return
        self.descending = (
            not self.descending if column == self.sort_column else False
        )
        self.sort_column = column
        self.page = 1

    @rx.event
    def clear_filters(self):
        self.query = ""
        self.store = ""
        self.page = 1

    @rx.event
    def previous(self):
        self.page = max(1, self.page - 1)

    @rx.event
    def next_page(self):
        self.page = min(self.pages, self.page + 1)
