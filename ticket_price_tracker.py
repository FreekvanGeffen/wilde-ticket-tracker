#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


EUR_PRICE_RE = re.compile(r"€\s*([0-9]+[.,][0-9]{2})")
SOLD_PATTERNS = [
    re.compile(r"([0-9][0-9.,]*)\s*(?:tickets?\s*)?sold", re.IGNORECASE),
    re.compile(r"sold\s*:?\s*([0-9][0-9.,]*)", re.IGNORECASE),
    re.compile(r"([0-9][0-9.,]*)\s*(?:tickets?\s*)?verkocht", re.IGNORECASE),
    re.compile(r"verkocht\s*:?\s*([0-9][0-9.,]*)", re.IGNORECASE),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track the lowest ticket resale price on a webpage."
    )
    parser.add_argument(
        "--url",
        default="https://resale.paylogic.com/a5c8fdff7b104c058a39dba53842993d/d366ae231edf4164ab8a01ac78767ade",
        help="Page URL to monitor.",
    )
    parser.add_argument(
        "--csv",
        default="ticket_price_history.csv",
        help="CSV output file path.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30000,
        help="Navigation timeout in milliseconds.",
    )
    return parser.parse_args()


def extract_prices_from_text(text: str) -> list[float]:
    prices: list[float] = []
    for match in EUR_PRICE_RE.findall(text):
        normalized = match.strip()
        if "," in normalized:
            normalized = normalized.replace(",", ".")
        try:
            prices.append(float(normalized))
        except ValueError:
            continue
    return prices


def extract_sold_tickets_from_text(text: str) -> int | None:
    values: list[int] = []
    for pattern in SOLD_PATTERNS:
        for raw in pattern.findall(text):
            cleaned = re.sub(r"[.,](?=\d{3}\b)", "", raw)
            cleaned = cleaned.replace(",", "")
            try:
                values.append(int(cleaned))
            except ValueError:
                continue
    if not values:
        return None
    return max(values)


def count_available_tickets_from_text(text: str) -> int:
    # Each listed ticket mentions statiegeld once on this page.
    return len(re.findall(r"statiegeld", text, re.IGNORECASE))


def fetch_ticket_data(url: str, timeout_ms: int) -> tuple[float | None, int | None, int | None]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            page.wait_for_timeout(2500)
            # Prices are shown after selecting this ticket type.
            page.get_by_text("Weekend + Camping", exact=False).first.click(timeout=timeout_ms)
            page.wait_for_timeout(2500)
            text = page.inner_text("body")
        except PlaywrightTimeoutError:
            browser.close()
            return None, None, None
        except Exception:
            try:
                # Fallback selector strategy for different markup variants.
                page.locator(
                    "text=/Weekend\\s*\\+\\s*Camping/i"
                ).first.click(timeout=timeout_ms)
                page.wait_for_timeout(2500)
                text = page.inner_text("body")
            except Exception:
                browser.close()
                return None, None, None
        browser.close()

    prices = extract_prices_from_text(text)
    lowest_price = min(prices) if prices else None
    sold_tickets = extract_sold_tickets_from_text(text)
    available_tickets = count_available_tickets_from_text(text)
    return lowest_price, sold_tickets, available_tickets


def append_row(
    csv_path: Path,
    date: str,
    time: str,
    lowest_price: float | None,
    sold_tickets: int | None,
    available_tickets: int | None,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(
                ["date", "time", "lowest_price_eur", "sold_tickets", "available_tickets"]
            )
        writer.writerow(
            [
                date,
                time,
                "" if lowest_price is None else f"{lowest_price:.2f}",
                "" if sold_tickets is None else sold_tickets,
                "" if available_tickets is None else available_tickets,
            ]
        )


def main() -> None:
    args = parse_args()
    now = dt.datetime.now(ZoneInfo("Europe/Amsterdam")).replace(microsecond=0)
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    lowest, sold_tickets, available_tickets = fetch_ticket_data(args.url, args.timeout_ms)
    append_row(Path(args.csv), date, time, lowest, sold_tickets, available_tickets)

    price_text = "No price found" if lowest is None else f"Lowest price: EUR {lowest:.2f}"
    sold_text = (
        "sold tickets: unknown"
        if sold_tickets is None
        else f"sold tickets: {sold_tickets}"
    )
    available_text = (
        "available tickets: unknown"
        if available_tickets is None
        else f"available tickets: {available_tickets}"
    )
    print(f"[{date} {time}] {price_text} | {sold_text} | {available_text}")


if __name__ == "__main__":
    main()
