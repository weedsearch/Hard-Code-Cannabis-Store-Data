import reflex as rx
from urllib.parse import urlsplit
from app.snapshot import RETAILERS, Retailer


class DirectoryState(rx.State):
    query: str = ""
    designation: str = "All designations"
    sort_column: str = "name"
    descending: bool = False
    page: int = 1

    @rx.var
    def designations(self) -> list[str]:
        return [
            "All designations",
            *sorted({r["designation"] for r in RETAILERS if r["designation"]}),
        ]

    @rx.var
    def filtered(self) -> list[Retailer]:
        terms = self.query.casefold().split()
        rows = []
        for record in RETAILERS:
            haystack = " ".join(
                record[k] for k in ("name", "address", "town", "zip")
            ).casefold()
            if all(term in haystack for term in terms) and (
                self.designation == "All designations"
                or record["designation"] == self.designation
            ):
                rows.append(record)
        return sorted(
            rows,
            key=lambda r: (
                r[self.sort_column].casefold(),
                r["name"].casefold(),
                r["id"],
            ),
            reverse=self.descending,
        )

    @rx.var
    def total(self) -> int:
        return len(RETAILERS)

    @rx.var
    def count(self) -> int:
        return len(self.filtered)

    @rx.var
    def pages(self) -> int:
        return max(1, (self.count + 24) // 25)

    @rx.var
    def visible_rows(self) -> list[Retailer]:
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
    def filter_designation(self, value: str):
        self.designation = value
        self.page = 1

    @rx.event
    def sort_by(self, column: str):
        if column not in ("name", "town", "designation"):
            return
        self.descending = (
            not self.descending if column == self.sort_column else False
        )
        self.sort_column = column
        self.page = 1

    @rx.event
    def clear_filters(self):
        self.query = ""
        self.designation = "All designations"
        self.page = 1

    @rx.event
    def previous(self):
        self.page = max(1, self.page - 1)

    @rx.event
    def next_page(self):
        self.page = min(self.pages, self.page + 1)
