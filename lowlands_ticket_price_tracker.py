#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


RESALE_LISTING_RE = re.compile(
    r"Verified Resale Ticket\s+(\d+)\s+beschikbaar.*?€\s*([0-9]+[.,][0-9]{2})\s*per stuk",
    re.IGNORECASE | re.DOTALL,
)
PRIMARY_PRICE_RE = re.compile(
    r"Regulier\s+€\s*([0-9]+[.,][0-9]{2}),\s*Huidig aantal",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track Lowlands 2026 verified resale prices on Ticketmaster."
    )
    parser.add_argument(
        "--url",
        default=(
            "https://www.ticketmaster.nl/event/"
            "lowlands-2026-festivalticket-tickets/1050736969"
        ),
        help="Ticketmaster event URL to monitor.",
    )
    parser.add_argument(
        "--csv",
        default="lowlands_ticket_price_history.csv",
        help="CSV output file path.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=45000,
        help="Navigation timeout in milliseconds.",
    )
    return parser.parse_args()


def normalize_price(raw: str) -> float | None:
    normalized = raw.strip()
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def dismiss_cookie_banner(page, timeout_ms: int) -> None:
    for label in ("Accept Cookies", "Reject All"):
        try:
            page.get_by_role("button", name=label, exact=True).click(timeout=3000)
            page.wait_for_timeout(1000)
            return
        except Exception:
            continue


def fetch_ticket_data(url: str, timeout_ms: int) -> tuple[float | None, int | None, float | None]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            locale="nl-NL",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            dismiss_cookie_banner(page, timeout_ms)
            page.wait_for_timeout(3000)
            text = page.inner_text("body")
        except PlaywrightTimeoutError:
            browser.close()
            return None, None, None
        except Exception:
            browser.close()
            return None, None, None
        browser.close()

    resale_prices: list[float] = []
    available_tickets = 0
    for count_raw, price_raw in RESALE_LISTING_RE.findall(text):
        price = normalize_price(price_raw)
        if price is not None:
            resale_prices.append(price)
        try:
            available_tickets += int(count_raw)
        except ValueError:
            continue

    lowest_resale = min(resale_prices) if resale_prices else None

    primary_match = PRIMARY_PRICE_RE.search(text)
    primary_price = (
        normalize_price(primary_match.group(1)) if primary_match else None
    )

    return lowest_resale, available_tickets or None, primary_price


def append_row(
    csv_path: Path,
    date: str,
    time: str,
    lowest_resale_price: float | None,
    available_resale_tickets: int | None,
    primary_price: float | None,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(
                [
                    "date",
                    "time",
                    "lowest_resale_price_eur",
                    "available_resale_tickets",
                    "primary_price_eur",
                ]
            )
        writer.writerow(
            [
                date,
                time,
                "" if lowest_resale_price is None else f"{lowest_resale_price:.2f}",
                "" if available_resale_tickets is None else available_resale_tickets,
                "" if primary_price is None else f"{primary_price:.2f}",
            ]
        )


def main() -> None:
    args = parse_args()
    now = dt.datetime.now(ZoneInfo("Europe/Amsterdam")).replace(microsecond=0)
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    lowest, available, primary = fetch_ticket_data(args.url, args.timeout_ms)
    append_row(Path(args.csv), date, time, lowest, available, primary)

    price_text = (
        "No resale price found"
        if lowest is None
        else f"Lowest resale price: EUR {lowest:.2f}"
    )
    available_text = (
        "available resale tickets: unknown"
        if available is None
        else f"available resale tickets: {available}"
    )
    primary_text = (
        "primary price: unknown"
        if primary is None
        else f"primary price: EUR {primary:.2f}"
    )
    print(f"[{date} {time}] {price_text} | {available_text} | {primary_text}")


if __name__ == "__main__":
    main()
