import reflex as rx
from app.components.registry import registry
from app.snapshot import SOURCE_URL


def index() -> rx.Component:
    return rx.el.main(
        rx.el.header(
            rx.el.div(
                rx.el.span(
                    "MASSACHUSETTS",
                    class_name="text-xs font-semibold tracking-[0.22em]",
                ),
                rx.el.span(
                    "PUBLIC DATA / RETAILER REGISTRY",
                    class_name="text-[10px] tracking-[0.14em] text-[#c8d5c7]",
                ),
                class_name="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-6 py-5 md:px-12",
            ),
            class_name="border-t-4 border-[#873849] bg-[#193f33] text-[#f7f7ec]",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    "THE COMMONWEALTH • CANNABIS DIRECTORY",
                    class_name="mb-5 text-[10px] font-semibold tracking-[0.18em] text-[#687760]",
                ),
                rx.el.div(
                    rx.el.h1(
                        "Massachusetts Cannabis",
                        rx.el.br(),
                        "Retailer Directory",
                        class_name="font-serif text-4xl leading-[1.12] tracking-tight text-[#1d4232] md:text-5xl",
                    ),
                    rx.el.div(
                        rx.icon("archive", class_name="h-4 w-4"),
                        "Public-source snapshot loaded at server startup",
                        class_name="flex w-fit items-center gap-2 border-y border-[#bdc8b5] py-3 text-xs text-[#516549]",
                    ),
                    class_name="flex flex-col justify-between gap-6 md:flex-row md:items-end",
                ),
                rx.el.p(
                    "Find retailer locations, designations and contact details across Massachusetts.",
                    class_name="mt-5 text-sm leading-6 text-[#606c56]",
                ),
                class_name="pb-8 pt-10 md:pt-14",
            ),
            registry(),
            rx.el.footer(
                rx.el.div(
                    rx.el.p(
                        "ABOUT THIS DATA",
                        class_name="mb-2 text-[10px] font-semibold tracking-[0.15em] text-[#355238]",
                    ),
                    rx.el.p(
                        "This directory uses a public-source snapshot loaded at server startup. Records are not continuously refreshed. Business details may change; confirm current details and availability directly with the retailer.",
                        class_name="max-w-2xl text-xs leading-6 text-[#687260]",
                    ),
                ),
                rx.el.a(
                    "Source: Cannabis Control Commission",
                    rx.icon("arrow-up-right", class_name="h-3.5 w-3.5"),
                    href=SOURCE_URL,
                    target="_blank",
                    rel="noopener noreferrer",
                    class_name="flex items-center gap-2 text-xs text-[#36563e] underline underline-offset-4 hover:text-[#8b3445]",
                ),
                class_name="mt-8 flex flex-col justify-between gap-6 border-t border-[#bdc7b5] py-8 md:flex-row md:items-start",
            ),
            class_name="mx-auto w-full max-w-[1440px] px-6 md:px-12",
        ),
        class_name="min-h-screen bg-[#f8f7ef] font-['Inter'] text-[#344c38] selection:bg-[#dce5cc]",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            cross_origin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(
    index,
    route="/",
    title="Massachusetts Cannabis Retailer Directory",
    description="Search a public-source snapshot loaded at server startup of Massachusetts cannabis retailer records. Confirm current details with the retailer.",
)
