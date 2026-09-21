import reflex as rx
from app.snapshot import Retailer
from app.states.directory import DirectoryState as S


def sort_heading(label: str, column: str) -> rx.Component:
    return rx.el.th(
        rx.el.button(
            label,
            rx.icon(
                tag=rx.cond(
                    S.sort_column == column,
                    rx.cond(S.descending, "arrow-down", "arrow-up"),
                    "arrow-up-down",
                ),
                class_name="h-3.5 w-3.5",
            ),
            on_click=S.sort_by(column),
            class_name="flex items-center gap-2 py-4 hover:text-[#8b3445] focus-visible:outline-2 focus-visible:outline-offset-4",
        ),
        scope="col",
        aria_sort=rx.cond(
            S.sort_column == column,
            rx.cond(S.descending, "descending", "ascending"),
            "none",
        ),
        class_name="px-5 text-left text-xs font-semibold",
    )


def retailer_row(row: Retailer) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.p(row["name"], class_name="font-semibold text-[#183f35]"),
            rx.el.p(
                f"Record {row['id']}",
                class_name="mt-1 text-[11px] text-[#74776e]",
            ),
            class_name="px-5 py-5 min-w-56",
        ),
        rx.el.td(
            rx.el.p(
                rx.cond(
                    row["address"] != "", row["address"], "Address not listed"
                )
            ),
            rx.el.p(
                f"{row['state']} {row['zip']}",
                class_name="mt-1 text-xs text-[#74776e] tabular-nums",
            ),
            class_name="px-5 py-5 min-w-52",
        ),
        rx.el.td(row["town"], class_name="px-5 py-5"),
        rx.el.td(
            rx.el.span(
                row["designation"],
                class_name=rx.cond(
                    row["designation"] == "Medical",
                    "inline-block w-fit rounded-sm bg-[#eee6e7] px-2 py-1 text-xs text-[#813747]",
                    "inline-block w-fit rounded-sm bg-[#e6eee7] px-2 py-1 text-xs text-[#27523e]",
                ),
            ),
            rx.el.p(
                row["priority"],
                class_name="mt-2 max-w-48 text-[11px] text-[#74776e]",
            ),
            class_name="px-5 py-5",
        ),
        rx.el.td(
            rx.el.p(
                rx.cond(row["phone"] != "", row["phone"], "Phone not listed"),
                class_name="whitespace-nowrap text-xs",
            ),
            rx.cond(
                row["website"].startswith("https://")
                | row["website"].startswith("http://"),
                rx.el.a(
                    "Visit website",
                    rx.icon("arrow-up-right", class_name="h-3 w-3"),
                    href=row["website"],
                    target="_blank",
                    rel="noopener noreferrer",
                    class_name="mt-2 inline-flex items-center gap-1 text-xs text-[#27523e] underline underline-offset-4 hover:text-[#8b3445]",
                ),
                rx.el.p(
                    "Website not listed",
                    class_name="mt-2 text-xs text-[#74776e]",
                ),
            ),
            class_name="px-5 py-5",
        ),
        key=row["id"],
        class_name="border-b border-[#dedfd4] bg-[#faf9f4] even:bg-[#f3f3eb] hover:bg-[#ecf0e7] transition-colors align-top text-sm text-[#494f46]",
    )


def controls() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.label(
                "SEARCH THE REGISTRY",
                html_for="registry-search",
                class_name="mb-2 block text-[10px] font-semibold tracking-[0.14em] text-[#4e5d50]",
            ),
            rx.el.div(
                rx.icon(
                    "search",
                    class_name="absolute left-4 top-3.5 h-4 w-4 text-[#667464]",
                ),
                rx.el.input(
                    id="registry-search",
                    placeholder="Search by name, street, town or ZIP code",
                    default_value=S.query,
                    on_change=S.search.debounce(300),
                    class_name="h-11 w-full border border-[#bdc8b9] bg-[#fffef9] pl-11 pr-4 text-sm text-[#223f33] placeholder:text-[#7d8478] focus:outline-2 focus:outline-[#315e45]",
                ),
                class_name="relative",
            ),
            class_name="flex-1 min-w-0",
        ),
        rx.el.div(
            rx.el.label(
                "DESIGNATION",
                html_for="designation",
                class_name="mb-2 block text-[10px] font-semibold tracking-[0.14em] text-[#4e5d50]",
            ),
            rx.el.div(
                rx.el.select(
                    rx.foreach(
                        S.designations,
                        lambda item: rx.el.option(item, value=item),
                    ),
                    id="designation",
                    value=S.designation,
                    on_change=S.filter_designation,
                    class_name="h-11 w-full appearance-none border border-[#bdc8b9] bg-[#fffef9] px-4 pr-10 text-sm text-[#223f33] focus:outline-2 focus:outline-[#315e45]",
                ),
                rx.icon(
                    "chevron-down",
                    class_name="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-[#53614f]",
                ),
                class_name="relative",
            ),
            class_name="w-full sm:w-60",
        ),
        rx.el.button(
            "Clear filters",
            on_click=S.clear_filters,
            class_name="h-11 px-1 text-xs text-[#52604f] underline underline-offset-4 hover:text-[#8b3445]",
        ),
        class_name="flex flex-col gap-5 sm:flex-row sm:items-end border-y border-[#b9c6b4] bg-[#edf0e5] px-5 py-6",
    )


def registry() -> rx.Component:
    return rx.el.section(
        controls(),
        rx.el.div(
            rx.el.p(
                rx.el.span(S.count, class_name="font-semibold text-[#193f33]"),
                " records found",
                role="status",
            ),
            rx.el.p("25 records per page", class_name="text-[#777b70]"),
            class_name="flex justify-between py-5 text-xs text-[#54604f]",
        ),
        rx.cond(
            S.count > 0,
            rx.el.div(
                rx.el.table(
                    rx.el.caption(
                        "Massachusetts cannabis retailer registry",
                        class_name="sr-only",
                    ),
                    rx.el.thead(
                        rx.el.tr(
                            sort_heading("Retailer name", "name"),
                            rx.el.th(
                                "Street address / ZIP",
                                scope="col",
                                class_name="px-5 py-4 text-left text-xs font-semibold",
                            ),
                            sort_heading("Town", "town"),
                            sort_heading("Designation", "designation"),
                            rx.el.th(
                                "Contact",
                                scope="col",
                                class_name="px-5 py-4 text-left text-xs font-semibold",
                            ),
                        ),
                        class_name="border-y border-[#bec9b7] bg-[#e8ecdf] text-[#314c38]",
                    ),
                    rx.el.tbody(rx.foreach(S.visible_rows, retailer_row)),
                    class_name="table-auto w-full min-w-[850px]",
                ),
                class_name="w-full overflow-x-auto border-b border-[#bbc5b5]",
            ),
            rx.el.div(
                rx.icon(
                    "search-x", class_name="mx-auto mb-4 h-7 w-7 text-[#7e8b77]"
                ),
                rx.el.h3(
                    "No matching records",
                    class_name="font-serif text-2xl text-[#244833]",
                ),
                rx.el.p(
                    "Try a different name or ZIP code, or clear your designation filter.",
                    class_name="mt-2 text-sm text-[#72786b]",
                ),
                rx.el.button(
                    "Clear all filters",
                    on_click=S.clear_filters,
                    class_name="mt-5 bg-[#224b39] px-5 py-2 text-sm text-white hover:bg-[#356348]",
                ),
                class_name="border-y border-[#c9cebe] py-16 text-center",
            ),
        ),
        rx.el.div(
            rx.el.p(
                S.range_label,
                class_name="text-xs text-[#626c5d]",
                role="status",
            ),
            rx.el.div(
                rx.el.button(
                    rx.icon("chevron-left", class_name="h-4 w-4"),
                    "Previous",
                    disabled=S.page <= 1,
                    on_click=S.previous,
                    class_name="flex items-center gap-1 border border-[#c3cbba] px-3 py-2 text-xs hover:bg-[#e7ebdf] disabled:opacity-40 disabled:cursor-not-allowed",
                ),
                rx.el.span(
                    f"Page {S.page} of {S.pages}",
                    class_name="px-2 text-xs tabular-nums",
                ),
                rx.el.button(
                    "Next",
                    rx.icon("chevron-right", class_name="h-4 w-4"),
                    disabled=S.page >= S.pages,
                    on_click=S.next_page,
                    class_name="flex items-center gap-1 border border-[#c3cbba] px-3 py-2 text-xs hover:bg-[#e7ebdf] disabled:opacity-40 disabled:cursor-not-allowed",
                ),
                class_name="flex items-center gap-2 text-[#36513c]",
            ),
            class_name="flex flex-wrap items-center justify-between gap-4 py-6",
        ),
        aria_label="Searchable retailer registry",
    )
