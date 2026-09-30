#!/usr/bin/env python3
"""One-shot SmartStore stock check for scheduled cloud runners."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PRODUCT_URL = os.getenv(
    "PRODUCT_URL",
    "https://smartstore.naver.com/panasonickorea/products/13726282633",
)
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "").strip()
NTFY_URL = "https://ntfy.sh"
STATE_PATH = Path("monitor_state.json")

OUT_TERMS = ("품절", "일시 품절", "일시품절", "구매 불가", "구매불가", "판매 종료", "판매종료")
IN_TERMS = ("구매하기", "바로구매", "장바구니", "주문하기")
MISSING_TERMS = ("상품이 없습니다", "상품을 찾을 수 없습니다", "존재하지 않는 상품")
PAGE_ERROR_TERMS = (
    "에러 페이지",
    "에러페이지",
    "오류 페이지",
    "오류페이지",
    "시스템 오류",
    "시스템오류",
    "요청이 너무 많",
    "접속이 원활하지",
    "접근이 제한",
    "비정상적인 접근",
    "too many requests",
    "access denied",
    "temporarily unavailable",
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def has_term(text: str, terms: tuple[str, ...]) -> bool:
    normalized = normalize(text)
    return any(normalize(term) in normalized for term in terms)


def classify(title: str, body: str, controls: str) -> str:
    if has_term(title + " " + body[:8000], MISSING_TERMS):
        return "PAGE_UNAVAILABLE"

    out_control = has_term(controls, OUT_TERMS)
    enabled_in_control = any(
        has_term(line, IN_TERMS) and "[disabled]" not in line
        for line in controls.splitlines()
    )

    if out_control and enabled_in_control:
        return "UNKNOWN"
    if out_control:
        return "OUT_OF_STOCK"
    if enabled_in_control:
        return "IN_STOCK"

    out_text = has_term(body[:12000], OUT_TERMS)
    in_text = has_term(body[:12000], IN_TERMS)
    if out_text and not in_text:
        return "OUT_OF_STOCK"
    if in_text and not out_text:
        return "IN_STOCK"
    return "UNKNOWN"


def is_unavailable_page(title: str, body: str, http_status: int | None) -> bool:
    # Never infer stock from an HTTP error or an interstitial/error page. These
    # pages can contain shared navigation text such as "구매하기".
    if http_status != 200:
        return True
    return has_term(title + " " + body[:8000], PAGE_ERROR_TERMS)


def read_product() -> tuple[str, str, str, int | None]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="ko-KR")
        try:
            response = page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=50_000)
            page.wait_for_timeout(6_000)
            title = page.title()
            body = page.locator("body").inner_text(timeout=15_000)
            visible = []
            for control in page.locator("button:visible, [role=button]:visible").all():
                try:
                    label = control.inner_text(timeout=1_000).strip()
                    disabled = control.is_disabled() or control.get_attribute("aria-disabled") == "true"
                    if label:
                        visible.append(f"{label} [disabled]" if disabled else label)
                except Exception:
                    continue
            return title, body, "\n".join(visible), response.status if response else None
        finally:
            browser.close()


def send_push(title: str, message: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", NTFY_TOPIC):
        raise RuntimeError("NTFY_TOPIC secret is missing or malformed.")
    response = requests.post(
        f"{NTFY_URL}/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "high",
            "Click": PRODUCT_URL,
        },
        timeout=20,
    )
    response.raise_for_status()


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"last_known_status": None, "test_sent": False, "last_heartbeat_date": None}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if not NTFY_TOPIC:
        print("::error::Add a repository Actions secret named NTFY_TOPIC.")
        return 2

    state = load_state()

    if not state.get("test_sent"):
        send_push("Restock monitor connected", "클라우드 감시기와 휴대폰 알림 연결이 완료됐습니다.")
        state["test_sent"] = True
        save_state(state)
        print("Phone push connection test sent.")

    try:
        title, body, controls, http_status = read_product()
    except PlaywrightTimeoutError as exc:
        print(f"::warning::Product page timed out: {exc}")
        return 0
    except Exception as exc:
        print(f"::warning::Could not read product page: {type(exc).__name__}: {exc}")
        return 0

    if is_unavailable_page(title, body, http_status):
        status = "PAGE_UNAVAILABLE"
    else:
        status = classify(title, body, controls)
    now = datetime.now(timezone.utc)
    print(f"Checked {PRODUCT_URL}")
    print(f"Page title: {title}")
    print(f"HTTP status: {http_status}")
    print(f"Detected state: {status}")

    if status == "PAGE_UNAVAILABLE":
        # A prior state inferred from an error page is not trustworthy. Reset it
        # so a later successful read can generate a fresh alert if appropriate.
        state["last_known_status"] = None
        print(f"::warning::Could not verify product stock (HTTP {http_status}); no restock alert was sent.")
    elif status == "UNKNOWN":
        print("Visible buy controls:", controls[:800] or "(none)")
        clues = [line.strip() for line in body.splitlines() if has_term(line, OUT_TERMS + IN_TERMS)]
        if clues:
            print("Stock text:", " | ".join(clues[:8])[:800])
    else:
        previous = state.get("last_known_status")
        if status == "IN_STOCK" and previous != "IN_STOCK":
            send_push(
                "SmartStore restock detected",
                "상품을 구매할 수 있는 것으로 감지했습니다. 재고가 남아 있을 때 확인하세요.",
            )
            print("Restock push sent.")
        state["last_known_status"] = status

    # A daily state update keeps the scheduled public-repository workflow active.
    state["last_heartbeat_date"] = now.date().isoformat()
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
