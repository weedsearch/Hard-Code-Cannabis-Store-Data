import reflex as rx
from app.flower_data import Flower
from app.states.flowers import FlowerState as S


def flower_heading(label: str, column: str) -> rx.Component:
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
            class_name="flex items-center gap-2 py-4 hover:text-[#8b3445] focus-visible:outline-2",
        ),
        scope="col",
        aria_sort=rx.cond(
            S.sort_column == column,
            rx.cond(S.descending, "descending", "ascending"),
            "none",
        ),
        class_name="px-5 text-left text-xs font-semibold",
    )


def flower_row(row: Flower) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            row["name"],
            class_name="min-w-56 px-5 py-4 font-semibold text-[#183f35]",
        ),
        rx.foreach(
            ["thc", "price", "weight"],
            lambda field: rx.el.td(
                rx.cond(row[field] != "", row[field], "—"),
                class_name="px-5 py-4 tabular-nums",
            ),
        ),
        rx.el.td(row["store"], class_name="min-w-56 px-5 py-4"),
        rx.el.td(
            rx.cond(
                row["source_url"] != "",
                rx.el.a(
                    row["provider"],
                    rx.icon("arrow-up-right", class_name="h-3 w-3"),
                    href=row["source_url"],
                    target="_blank",
                    rel="noopener noreferrer nofollow",
                    class_name="inline-flex items-center gap-1 text-[#27523e] underline underline-offset-4 hover:text-[#8b3445]",
                ),
                rx.el.span("Not available"),
            ),
            class_name="px-5 py-4 text-xs",
        ),
        class_name="border-b border-[#dedfd4] bg-[#faf9f4] even:bg-[#f3f3eb] hover:bg-[#ecf0e7] align-top text-sm text-[#494f46]",
    )


def flower_controls() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.label(
                "SEARCH FLOWER",
                html_for="flower-search",
                class_name="mb-2 block text-[10px] font-semibold tracking-[0.14em] text-[#4e5d50]",
            ),
            rx.el.div(
                rx.icon(
                    "search",
                    class_name="absolute left-4 top-3.5 h-4 w-4 text-[#667464]",
                ),
                rx.el.input(
                    id="flower-search",
                    placeholder="Search product, THC, weight or store",
                    default_value=S.query,
                    on_change=S.search.debounce(300),
                    class_name="h-11 w-full border border-[#bdc8b9] bg-[#fffef9] pl-11 pr-4 text-sm text-[#223f33] focus:outline-2 focus:outline-[#315e45]",
                ),
                class_name="relative",
            ),
            class_name="min-w-0 flex-1",
        ),
        rx.el.div(
            rx.el.label(
                "STORE / LOCATION",
                html_for="flower-store",
                class_name="mb-2 block text-[10px] font-semibold tracking-[0.14em] text-[#4e5d50]",
            ),
            rx.el.div(
                rx.el.select(
                    rx.el.option("All stores", value=""),
                    rx.foreach(
                        S.stores, lambda store: rx.el.option(store, value=store)
                    ),
                    id="flower-store",
                    value=S.store,
                    on_change=S.filter_store,
                    class_name="h-11 w-full appearance-none border border-[#bdc8b9] bg-[#fffef9] px-4 pr-10 text-sm text-[#223f33] focus:outline-2 focus:outline-[#315e45]",
                ),
                rx.icon(
                    "chevron-down",
                    class_name="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-[#53614f]",
                ),
                class_name="relative",
            ),
            class_name="w-full sm:w-72",
        ),
        rx.el.button(
            "Clear filters",
            on_click=S.clear_filters,
            class_name="h-11 text-xs text-[#52604f] underline underline-offset-4 hover:text-[#8b3445]",
        ),
        class_name="flex flex-col gap-5 border-y border-[#b9c6b4] bg-[#edf0e5] px-5 py-6 sm:flex-row sm:items-end",
    )


def flower_table() -> rx.Component:
    return rx.el.div(
        flower_controls(),
        rx.el.div(
            rx.el.p(S.range_label, role="status"),
            rx.el.p("25 listings per page"),
            class_name="flex justify-between py-5 text-xs text-[#54604f]",
        ),
        rx.cond(
            S.count > 0,
            rx.el.div(
                rx.el.table(
                    rx.el.caption(
                        "Public flower-menu snapshot; a dash indicates a value not provided by the source.",
                        class_name="sr-only",
                    ),
                    rx.el.thead(
                        rx.el.tr(
                            flower_heading("Strain / product", "name"),
                            rx.foreach(
                                ["THC", "Price", "Weight"],
                                lambda label: rx.el.th(
                                    label,
                                    scope="col",
                                    class_name="px-5 py-4 text-left text-xs font-semibold",
                                ),
                            ),
                            flower_heading("Store", "store"),
                            rx.el.th(
                                "Source",
                                scope="col",
                                class_name="px-5 py-4 text-left text-xs font-semibold",
                            ),
                        ),
                        class_name="border-y border-[#bec9b7] bg-[#e8ecdf] text-[#314c38]",
                    ),
                    rx.el.tbody(rx.foreach(S.visible, flower_row)),
                    class_name="table-auto w-full min-w-[800px]",
                ),
                class_name="w-full overflow-x-auto border-b border-[#bbc5b5]",
            ),
            rx.el.div(
                rx.icon(
                    "leaf", class_name="mx-auto mb-3 h-6 w-6 text-[#687760]"
                ),
                rx.el.h3(
                    rx.cond(
                        S.rows.length() > 0,
                        "No matching flower listings",
                        "No ordinary flower listings could be parsed",
                    ),
                    class_name="font-serif text-2xl text-[#244833]",
                ),
                rx.el.p(
                    rx.cond(
                        S.rows.length() > 0,
                        "Try another search or clear your store filter.",
                        "Collection completed. See source coverage for the stores that could not be included.",
                    ),
                    class_name="mt-2 text-sm text-[#687260]",
                ),
                class_name="border-y border-[#c9cebe] py-12 text-center",
            ),
        ),
        rx.el.div(
            rx.el.p(
                "— Not listed by source", class_name="text-xs text-[#626c5d]"
            ),
            rx.el.div(
                rx.el.button(
                    rx.icon("chevron-left", class_name="h-4 w-4"),
                    "Previous",
                    on_click=S.previous,
                    disabled=S.page <= 1,
                    class_name="flex items-center gap-1 border border-[#c3cbba] px-3 py-2 text-xs hover:bg-[#e7ebdf] disabled:opacity-40",
                ),
                rx.el.span(
                    f"Page {S.page} of {S.pages}",
                    class_name="text-xs tabular-nums",
                ),
                rx.el.button(
                    "Next",
                    rx.icon("chevron-right", class_name="h-4 w-4"),
                    on_click=S.next_page,
                    disabled=S.page >= S.pages,
                    class_name="flex items-center gap-1 border border-[#c3cbba] px-3 py-2 text-xs hover:bg-[#e7ebdf] disabled:opacity-40",
                ),
                class_name="flex items-center gap-3 text-[#36513c]",
            ),
            class_name="flex flex-wrap items-center justify-between gap-4 py-6",
        ),
    )


def flower_snapshot() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.icon("leaf", class_name="h-6 w-6 text-[#687760]"),
            rx.el.p(
                "PUBLIC MENUS / ONE-TIME COLLECTION",
                class_name="text-[10px] font-semibold tracking-[0.18em] text-[#687760]",
            ),
            class_name="mb-4 flex items-center gap-3",
        ),
        rx.el.h2(
            "Flower Snapshot", class_name="font-serif text-3xl text-[#1d4232]"
        ),
        rx.el.p(
            "Menus change. Missing values were not inferred. Unreachable, blocked and unparseable stores are omitted from listings but counted in coverage. Product names are retained as published; they are not inferred strain names.",
            class_name="mt-3 mb-6 max-w-4xl text-xs leading-6 text-[#606c56]",
        ),
        rx.cond(
            S.loaded,
            rx.el.div(
                rx.el.p(
                    f"Captured: {S.captured_at}",
                    class_name="text-xs text-[#355238]",
                ),
                rx.el.p(
                    S.coverage_label,
                    class_name="mt-2 text-xs leading-6 text-[#606c56]",
                ),
                rx.el.details(
                    rx.el.summary(
                        "Source coverage breakdown",
                        class_name="cursor-pointer text-xs text-[#813747] underline underline-offset-4",
                    ),
                    rx.el.ul(
                        rx.foreach(
                            S.coverage_details,
                            lambda text: rx.el.li(text, class_name="py-1"),
                        ),
                        class_name="mt-3 columns-1 text-xs text-[#606c56] sm:columns-2",
                    ),
                    class_name="my-5",
                ),
                flower_table(),
            ),
            rx.el.div(
                rx.el.h3(
                    "No completed flower snapshot yet",
                    class_name="font-serif text-xl text-[#244833]",
                ),
                rx.el.p(
                    "A separate, read-only collection must finish before listings appear here. This page only reads the generated local snapshot and never crawls retailer menus.",
                    class_name="mt-2 max-w-2xl text-sm leading-6 text-[#687260]",
                ),
                rx.el.p(
                    "Collection may take multiple bounded runs. Partial results are not presented as a completed snapshot.",
                    class_name="mt-3 text-xs text-[#813747]",
                ),
                class_name="border-y border-[#bdc7b5] bg-[#f3f3eb] px-5 py-9",
            ),
        ),
        id="flower-snapshot",
        aria_label="Flower menu snapshot",
        class_name="mt-10 border-t-2 border-[#355238] pt-8",
    )
