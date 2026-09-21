import reflex as rx
import argparse
import fcntl
import hashlib
import ipaddress
import json
import logging
import re
import socket
import time
import os
import threading
from copy import deepcopy
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

REQUEST_TIMEOUT = 4
MAX_MENU_CANDIDATES = 3
MAX_WORKERS = 12
CHECKPOINT_RESERVE = 2
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qsl, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from app.flower_data import snapshot_path

UA = "MAFlowerSnapshot/1.0 (public menu research; read-only; robots compliant)"
FLOWER = {"flower", "flowers", "bud", "whole flower"}
EXCLUDE = re.compile(
    r"pre[ -]?roll|shake|trim|kief|infus|vape|cartridge|concentrate|extract|rosin|resin|hash|moon.?rock|multipack",
    re.I,
)
PROVIDERS = {
    "dutchie": ("dutchie",),
    "jane": ("iheartjane.com", "jane.com"),
    "dispense": ("dispenseapp", "dispense-images", "-dispense."),
    "sweed": ("sweed",),
    "leafly": ("leafly.com",),
    "weedmaps": ("weedmaps.com",),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def normalize_url(url: str) -> str:
    try:
        p = urlsplit(url.strip())
        if (
            p.scheme not in ("http", "https")
            or not p.hostname
            or p.username
            or p.password
        ):
            return ""
        host = p.hostname.lower()
        port = p.port
        netloc = host if port in (None, 80, 443) else f"{host}:{port}"
        query = urlencode(
            sorted(
                (k, v)
                for k, v in parse_qsl(p.query)
                if not k.lower().startswith("utm_")
                and k.lower() not in ("fbclid", "gclid")
            )
        )
        return urlunsplit(
            (p.scheme.lower(), netloc, p.path.rstrip("/") or "/", query, "")
        )
    except Exception as e:
        logging.exception(f"Error: {e}")
        return ""


def menu_rank(url: str, evidence: str = "") -> int:
    p = urlsplit(url)
    if re.search(
        r"checkout|cart|login|sign.?in|/api(?:/|$)|graphql|"
        r"/(?:about|contact|careers?|jobs?|blog|news|privacy|terms)(?:/|$)|"
        r"\.(?:pdf|js|css|png|jpe?g|svg|gif|webp|ico|woff2?|mp4)(?:$)",
        p.path,
        re.I,
    ) or re.search(r"checkout|cart|login|sign.?in|graphql", p.query, re.I):
        return -1
    marker = re.compile(
        r"(?<![a-z0-9])(?:dutchie|iheartjane|jane|dispenseapp|dispense|sweede?|leafly|weedmaps)(?![a-z0-9])",
        re.I,
    )
    provider_evidence = bool(marker.search(f"{p.hostname} {p.path} {evidence}"))
    for rank, term in enumerate(("menu", "shop", "order", "products"), start=1):
        if re.search(
            rf"(?:^|[/_-]){term}(?:$|[/_-])", p.path, re.I
        ) or re.search(rf"\b{term}\b", evidence, re.I):
            return 0 if provider_evidence else rank
    return 0 if provider_evidence else -1


def prune_menu_queue(target: dict, landing_url: str):
    """Count previously attempted candidates against the lifetime menu budget."""
    landing = normalize_url(landing_url)
    attempted = {
        normalized
        for value in target["seen"]
        for normalized in [normalize_url(value)]
        if normalized
    }
    attempted.update(
        normalized
        for source in target["sources"]
        for normalized in [normalize_url(source["url"])]
        if normalized
    )
    remaining = max(0, MAX_MENU_CANDIDATES - len(attempted - {landing}))
    scores = target.get("menu_scores", {})
    candidates: dict[str, int] = {}
    for value in target["queue"]:
        url = normalize_url(value)
        if not url or url == landing or url in attempted:
            continue
        rank = scores.get(url, menu_rank(url))
        if rank >= 0:
            candidates[url] = rank
    ranked = sorted(candidates, key=candidates.get)[:remaining]
    target["queue"] = (
        [landing] if landing and landing not in attempted else []
    ) + ranked
    if "menu_scores" in target:
        target["menu_scores"] = {url: candidates[url] for url in ranked}


def provider(url: str, soup: BeautifulSoup) -> str:
    evidence = " ".join(
        [
            url,
            *[
                str(tag.get("src", ""))
                for tag in soup.select("script[src], iframe[src]")
            ],
        ]
    ).lower()
    for name, markers in PROVIDERS.items():
        if any(marker in evidence for marker in markers):
            return name
    return "native"


def scalar(obj: dict, *keys: str) -> str:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            return str(value).strip()
    return ""


def parse_page(
    html: str, url: str, store: str, menu_scores: dict[str, int] | None = None
) -> tuple[list[dict], list[str], str]:
    soup = BeautifulSoup(html, "html.parser")
    vendor = provider(url, soup)
    rows: list[dict] = []

    def emit(obj: dict, category: str = ""):
        cat = (
            scalar(obj, "category", "productCategory", "product_type", "kind")
            or category
        )
        if isinstance(obj.get("category"), dict):
            cat = scalar(obj["category"], "name", "title")
        name = scalar(obj, "name", "product_name", "productName", "title")
        if (
            norm(cat) not in FLOWER
            or not name
            or EXCLUDE.search(f"{name} {cat} {scalar(obj, 'description')}")
        ):
            return
        variants = obj.get("variants", obj.get("offers", []))
        if isinstance(variants, dict):
            variants = [variants]
        if not isinstance(variants, list) or not variants:
            variants = [obj]
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            price = scalar(
                variant,
                "price_display",
                "priceDisplay",
                "price",
                "formattedPrice",
            )
            currency = scalar(variant, "priceCurrency")
            if price and currency:
                price = f"{price} {currency}"
            weight = scalar(
                variant, "weight_display", "weight", "weightLabel", "size"
            )
            if not weight and variant is obj:
                match = re.search(
                    r"\b\d+(?:\.\d+)?\s*(?:g|grams?|oz)\b|[⅛¼½]\s*oz",
                    name,
                    re.I,
                )
                weight = match.group(0) if match else ""
            thc = scalar(
                obj,
                "thc_display",
                "thcDisplay",
                "thc",
                "percent_thc",
                "thc_percent",
            )
            rows.append(
                dict(
                    name=name,
                    thc=thc,
                    price=price,
                    weight=weight,
                    store=store,
                    source_url=url,
                    provider=vendor,
                )
            )

    def walk(value: object, depth: int = 0):
        if depth > 40:
            return
        if isinstance(value, dict):
            emit(value)
            for child in value.values():
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)

    for script in soup.select(
        'script[type="application/ld+json"], script[type="application/json"], script#__NEXT_DATA__'
    ):
        try:
            walk(json.loads(script.string or script.get_text()))
        except Exception as e:
            logging.exception(f"Error: {e}")
    # Decode JSON literals only; never evaluate JavaScript or fetch script/API endpoints.
    decoder = json.JSONDecoder()
    for script in soup.find_all("script"):
        text = script.string or ""
        for match in re.finditer(
            r"(?:window\.)?__(?:INITIAL_STATE|PRELOADED_STATE|APOLLO_STATE)__\s*=\s*",
            text,
        ):
            try:
                value, _ = decoder.raw_decode(text[match.end() :].lstrip())
                walk(value)
            except Exception as e:
                logging.exception(f"Error: {e}")
    for card in soup.select(
        '[itemtype$="/Product"], [data-product], .product-card, .product'
    ):
        title = card.select_one(
            '[itemprop="name"], .product-title, .product-name, h2, h3'
        )
        category = card.select_one(
            '[itemprop="category"], .product-category, [data-category]'
        )
        cat = str(card.get("data-category", ""))
        if category:
            cat = category.get("content") or category.get_text(" ", strip=True)
        if not cat:
            section = card.find_parent("section")
            heading = section.find(["h1", "h2"]) if section else None
            cat = heading.get_text(" ", strip=True) if heading else ""
        data = {
            "name": title.get_text(" ", strip=True) if title else "",
            "category": cat,
        }
        for field, selector in {
            "price": '[itemprop="price"], .price',
            "weight": ".weight, [data-weight]",
            "thc": ".thc, [data-thc]",
        }.items():
            node = card.select_one(selector)
            data[field] = (
                str(node.get("content") or node.get_text(" ", strip=True))
                if node
                else ""
            )
        emit(data)
    candidates: dict[str, int] = {}
    for tag in soup.select("a[href], iframe[src]"):
        raw = str(tag.get("href") or tag.get("src") or "").strip()
        if not raw or raw.startswith("#"):
            continue
        target = normalize_url(urljoin(url, raw))
        if not target or target == normalize_url(url):
            continue
        label = " ".join(
            (
                tag.get_text(" ", strip=True),
                str(tag.get("title", "")),
                str(tag.get("aria-label", "")),
                str(tag.get("id", "")),
            )
        )
        rank = menu_rank(target, label)
        if rank >= 0:
            candidates[target] = min(rank, candidates.get(target, rank))
    links = sorted(candidates, key=candidates.get)[:MAX_MENU_CANDIDATES]
    if menu_scores is not None:
        menu_scores.update({link: candidates[link] for link in links})
    return rows, links, vendor


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Fetcher:
    def __init__(self, progress: dict, deadline: float):
        self.progress = {
            key: deepcopy(progress[key])
            for key in ("robots", "denied", "next_request")
        }
        self.deadline = deadline
        self.state_lock = threading.RLock()
        self.host_locks: dict[str, threading.RLock] = {}
        self.local = threading.local()

    def metadata(self) -> dict:
        with self.state_lock:
            return deepcopy(self.progress)

    def _get(self, section: str, key: str, default=None):
        with self.state_lock:
            return self.progress[section].get(key, default)

    def _set(self, section: str, key: str, value):
        with self.state_lock:
            self.progress[section][key] = value

    @contextmanager
    def _host_slot(self, url: str):
        p = urlsplit(url)
        if (
            p.scheme not in ("http", "https")
            or not p.hostname
            or p.username
            or p.password
        ):
            raise ValueError("Non-public destination")
        host = p.hostname.lower()
        with self.state_lock:
            lock = self.host_locks.setdefault(host, threading.RLock())
        remaining = self.deadline - time.monotonic() - REQUEST_TIMEOUT
        if remaining <= 0 or not lock.acquire(timeout=remaining):
            raise InterruptedError("Run budget reached")
        try:
            yield host
        finally:
            lock.release()

    def request(self, url: str, delay: float = 2) -> tuple[int, str, dict]:
        with self._host_slot(url):
            return self._request_locked(url, delay)

    def _request_locked(self, url: str, delay: float) -> tuple[int, str, dict]:
        p = urlsplit(url)
        if time.monotonic() + REQUEST_TIMEOUT >= self.deadline:
            raise InterruptedError("Run budget reached")
        addresses = socket.getaddrinfo(
            p.hostname, p.port or (443 if p.scheme == "https" else 80)
        )
        if not addresses or any(
            not ipaddress.ip_address(a[4][0]).is_global for a in addresses
        ):
            raise ValueError("Non-public destination")
        host = p.hostname.lower()
        pause = (
            max(
                self._get("next_request", host, 0),
                self._get("next_request", p.netloc, 0),
            )
            - time.time()
        )
        if time.monotonic() + max(0, pause) + REQUEST_TIMEOUT > self.deadline:
            raise InterruptedError("Run budget reached")
        if pause > 0:
            time.sleep(pause)
        if not hasattr(self.local, "opener"):
            self.local.opener = build_opener(NoRedirect())
        request_deadline = min(
            self.deadline, time.monotonic() + REQUEST_TIMEOUT
        )
        try:
            return self._read_response(url, request_deadline)
        finally:
            self._set("next_request", host, time.time() + max(2, delay))

    def _read_response(
        self, url: str, request_deadline: float
    ) -> tuple[int, str, dict]:
        try:
            response = self.local.opener.open(
                Request(
                    url,
                    headers={
                        "User-Agent": UA,
                        "Accept": "text/html,application/xhtml+xml,text/plain",
                    },
                    method="GET",
                ),
                timeout=min(
                    REQUEST_TIMEOUT,
                    max(0.001, request_deadline - time.monotonic()),
                ),
            )
        except HTTPError as e:
            # urllib represents non-2xx responses, including manual redirects, as HTTPError.
            logging.exception("Unexpected error")
            response = e
        with response:
            status = response.code
            headers = dict(response.headers)
            if status in (401, 403, 429):
                self._set(
                    "denied",
                    urlsplit(url).hostname.lower(),
                    "rate_limited" if status == 429 else "blocked",
                )
            raw = bytearray()
            while True:
                remaining = request_deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Response deadline reached")
                # Bound each read as well as the complete streamed body.
                connection = getattr(getattr(response, "fp", None), "raw", None)
                sock = getattr(connection, "_sock", None)
                if sock is not None:
                    sock.settimeout(min(REQUEST_TIMEOUT, remaining))
                chunk = response.read1(min(65536, 3_000_001 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > 3_000_000:
                    raise ValueError("Response exceeds size limit")
            body = raw.decode("utf-8", errors="replace")
        return status, body, headers

    def fetch(self, url: str) -> tuple[str, str, str]:
        for _ in range(6):
            with self._host_slot(url):
                status, body, url = self._fetch_hop(url)
            if status != "redirect":
                return status, body, url
        return "redirect_limit", "", url

    def _fetch_hop(self, url: str) -> tuple[str, str, str]:
        p = urlsplit(url)
        host = p.hostname.lower()
        origin = f"{p.scheme}://{p.netloc}"
        denied = self._get("denied", host) or self._get("denied", p.netloc)
        if denied:
            return denied, "", url
        robots = self._get("robots", origin)
        if robots is None:
            status, text, _headers = self.request(f"{origin}/robots.txt")
            if status in (404, 410) and "<html" not in text.lower():
                text = ""
            elif status != 200 or "<html" in text.lower():
                self._set("denied", host, "robots_unavailable")
                return "robots_unavailable", "", url
            self._set("robots", origin, text)
            robots = text
        parser = RobotFileParser()
        parser.parse(robots.splitlines())
        if not parser.can_fetch(UA, url):
            return "robots_denied", "", url
        delay = parser.crawl_delay(UA) or parser.crawl_delay("*") or 2
        rate = parser.request_rate(UA) or parser.request_rate("*")
        if rate:
            delay = max(delay, rate.seconds / rate.requests)
        # Apply a newly discovered crawl delay to the robots-to-page gap too.
        self._set(
            "next_request",
            host,
            max(
                self._get("next_request", host, 0),
                self._get("next_request", p.netloc, 0),
                time.time() + max(2, delay),
            ),
        )
        status, body, headers = self.request(url, delay)
        if status in (301, 302, 303, 307, 308):
            url = normalize_url(
                urljoin(
                    url,
                    headers.get("Location", headers.get("location", "")),
                )
            )
            if not url:
                return "unreachable", "", url
            return "redirect", "", url
        if status != 200:
            return (
                (
                    "rate_limited"
                    if status == 429
                    else "blocked"
                    if status in (401, 403)
                    else "unreachable"
                ),
                "",
                url,
            )
        visible = BeautifulSoup(body, "html.parser")
        for node in visible(["script", "style"]):
            node.decompose()
        text = visible.get_text(" ", strip=True).lower()
        if re.search(
            r"captcha|verify you are human|access denied|checking your browser|just a moment",
            text,
        ):
            self._set("denied", host, "blocked")
            return "blocked", "", url
        if re.search(
            r"are you (?:at least |over )?21|verify your age|age verification|enter your (?:date of birth|birthday)|must be 21.*enter",
            text,
        ):
            self._set("denied", host, "age_gate")
            return "age_gate", "", url
        if visible.select('input[type="password"]'):
            return "authentication", "", url
        if re.search(
            r"automated (?:access|collection|scraping).*prohibited|scraping is prohibited",
            text,
        ):
            return "blocked", "", url
        return "reachable_unparsed", body, url


def atomic_write(path, data: dict):
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("w") as file:
            json.dump(data, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    except Exception as e:
        logging.exception(f"Error: {e}")
        raise


def snapshot_progress(data: dict) -> dict:
    """Report discovered work only; queued sources may reveal further menu links."""
    targets = data["targets"]
    pending_sources = sum(len(target["queue"]) for target in targets)
    pending_targets = sum(bool(target["queue"]) for target in targets)
    processed_sources = sum(len(target["sources"]) for target in targets)
    status_counts: dict[str, int] = {}
    source_status_counts: dict[str, int] = {}
    retailer_status_counts: dict[str, int] = {}
    for target in targets:
        status = target["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        retailer_status_counts[status] = retailer_status_counts.get(
            status, 0
        ) + len(target["retailer_ids"])
        for source in target["sources"]:
            status = source["status"]
            source_status_counts[status] = (
                source_status_counts.get(status, 0) + 1
            )
    product_count = len(
        {
            tuple(
                norm(row[key]) for key in ("store", "name", "weight", "price")
            )
            for row in data["rows"]
        }
    )
    coverage = {
        "retailers": len(data["retailers"]),
        "unique_targets": len(targets),
        "sources": processed_sources,
        "listings": product_count,
        "parsed_retailers": retailer_status_counts.get("parsed", 0),
        "pending_targets": pending_targets,
        "pending_sources": pending_sources,
    }
    coverage.update(
        {f"sources_{key}": count for key, count in source_status_counts.items()}
    )
    coverage.update(
        {
            f"retailers_{key}": count
            for key, count in retailer_status_counts.items()
        }
    )
    return {
        "complete": False,
        "started_at": data["started_at"],
        "captured_at": data["captured_at"],
        "pending": pending_sources,
        "pending_sources": pending_sources,
        "pending_targets": pending_targets,
        "processed_targets": len(targets) - pending_targets,
        "total_targets": len(targets),
        "processed_sources": processed_sources,
        "total_sources": processed_sources + pending_sources,
        "row_count": len(data["rows"]),
        "product_count": product_count,
        "status_counts": status_counts,
        "source_status_counts": source_status_counts,
        "coverage": coverage,
    }


def collect_target(
    target: dict, fetcher: Fetcher, landing_url: str = ""
) -> tuple[dict, list[dict]]:
    """Own a private target copy and return completed work, including on budget expiry."""
    if not landing_url:
        landing_url = next(iter(target["seen"] or target["queue"]), "")
    landing_url = normalize_url(landing_url)
    prune_menu_queue(target, landing_url)
    collected: list[dict] = []
    while target["queue"]:
        if time.monotonic() + REQUEST_TIMEOUT >= fetcher.deadline:
            break
        url = target["queue"][0]
        try:
            status, html, final = fetcher.fetch(url)
            menu_scores: dict[str, int] = {}
            rows, links, vendor = (
                parse_page(html, final, target["store"], menu_scores)
                if html
                else ([], [], "unknown")
            )
            if rows:
                status = "parsed"
                collected.extend(rows)
            # Discover direct landing-page links only, never private API endpoints.
            if url == landing_url and html:
                target["menu_scores"] = menu_scores
                target["queue"].extend(u for u in links if u != url)
            source = {
                "url": url,
                "final_url": final,
                "status": status,
                "provider": vendor,
                "captured_at": now(),
                "sha256": hashlib.sha256(html.encode()).hexdigest()
                if html
                else "",
                "rows": len(rows),
            }
        except InterruptedError:
            logging.exception("Unexpected error")
            break
        except Exception as e:
            if not isinstance(e, (OSError, URLError, ValueError)):
                logging.exception(f"Error: {e}")
            status = (
                "timeout"
                if isinstance(e, TimeoutError)
                or isinstance(e, URLError)
                and isinstance(e.reason, TimeoutError)
                else "unreachable"
            )
            source = {
                "url": url,
                "final_url": url,
                "status": status,
                "provider": "unknown",
                "captured_at": now(),
                "rows": 0,
            }
        target["sources"].append(source)
        target["seen"].append(url)
        target["queue"].pop(0)
        prune_menu_queue(target, landing_url)
        target["status"] = (
            "parsed"
            if any(s["status"] == "parsed" for s in target["sources"])
            else status
        )
    return target, collected


def collect_snapshot(max_seconds: float = 120) -> dict:
    """Resume frozen targets concurrently; only the coordinator publishes checkpoints."""
    deadline = time.monotonic() + max(0, max_seconds) - CHECKPOINT_RESERVE
    path = snapshot_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            checkpoint = path.with_suffix(".progress.json")
            if path.exists():
                return json.loads(path.read_text())
            if checkpoint.exists():
                data = json.loads(checkpoint.read_text())
            else:
                from app.snapshot import RETAILERS

                targets = {}
                for retailer in RETAILERS:
                    url = normalize_url(retailer["website"])
                    location = norm(
                        f"{retailer['name']} {retailer['address']} {retailer['town']}"
                    )
                    key = f"{url}|{location}"
                    if key not in targets:
                        targets[key] = {
                            "store": f"{retailer['name']} — {retailer['address']}, {retailer['town']}",
                            "retailer_ids": [],
                            "queue": [url] if url else [],
                            "seen": [],
                            "sources": [],
                            "status": "pending" if url else "no_site",
                        }
                    targets[key]["retailer_ids"].append(retailer["id"])
                data = {
                    "version": 1,
                    "started_at": now(),
                    "captured_at": "",
                    "complete": False,
                    "retailers": RETAILERS,
                    "targets": list(targets.values()),
                    "rows": [],
                    "robots": {},
                    "denied": {},
                    "next_request": {},
                }
                atomic_write(checkpoint, data)
            retailer_urls = {
                retailer["id"]: normalize_url(retailer["website"])
                for retailer in data["retailers"]
            }
            landing_urls = [
                next(
                    (
                        retailer_urls[rid]
                        for rid in target["retailer_ids"]
                        if retailer_urls.get(rid)
                    ),
                    "",
                )
                for target in data["targets"]
            ]
            for target, landing_url in zip(data["targets"], landing_urls):
                prune_menu_queue(target, landing_url)
            atomic_write(checkpoint, data)
            fetcher = Fetcher(data, deadline)
            pending = iter(
                i for i, target in enumerate(data["targets"]) if target["queue"]
            )
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                active = {}
                exhausted = False
                while True:
                    while (
                        not exhausted
                        and len(active) < MAX_WORKERS
                        and time.monotonic() + REQUEST_TIMEOUT < deadline
                    ):
                        index = next(pending, None)
                        if index is None:
                            exhausted = True
                            break
                        future = executor.submit(
                            collect_target,
                            deepcopy(data["targets"][index]),
                            fetcher,
                            landing_urls[index],
                        )
                        active[future] = index
                    if not active:
                        break
                    completed, _ = wait(active, return_when=FIRST_COMPLETED)
                    for future in completed:
                        index = active.pop(future)
                        target, rows = future.result()
                        data["targets"][index] = target
                        data["rows"].extend(rows)
                    data.update(fetcher.metadata())
                    atomic_write(checkpoint, data)
            data.update(fetcher.metadata())
            atomic_write(checkpoint, data)
            if any(target["queue"] for target in data["targets"]):
                return snapshot_progress(data)
            unique = {}
            for row in data["rows"]:
                key = tuple(
                    norm(row[k]) for k in ("store", "name", "weight", "price")
                )
                unique.setdefault(key, row)
            statuses = []
            sources = []
            for target in data["targets"]:
                for rid in target["retailer_ids"]:
                    statuses.append(
                        {
                            "retailer_id": rid,
                            "store": target["store"],
                            "status": target["status"],
                            "sources": target["sources"],
                        }
                    )
                sources.extend(target["sources"])
            coverage = {
                "retailers": len(statuses),
                "unique_targets": len(data["targets"]),
                "sources": len(sources),
                "listings": len(unique),
                "parsed_retailers": sum(
                    s["status"] == "parsed" for s in statuses
                ),
                "omitted_retailers": sum(
                    s["status"] != "parsed" for s in statuses
                ),
            }
            for source in sources:
                key = f"sources_{source['status']}"
                coverage[key] = coverage.get(key, 0) + 1
            for record in statuses:
                key = f"retailers_{record['status']}"
                coverage[key] = coverage.get(key, 0) + 1
            result = {
                "version": 1,
                "complete": True,
                "started_at": data["started_at"],
                "captured_at": now(),
                "coverage": coverage,
                "statuses": statuses,
                "rows": list(unique.values()),
            }
            atomic_write(path, result)
            return result
    except Exception as e:
        logging.exception(f"Error: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect a resumable public flower-menu snapshot, without browser automation or private APIs."
    )
    parser.add_argument("--max-seconds", type=float, default=120)
    args = parser.parse_args()
    result = collect_snapshot(args.max_seconds)
    print(
        json.dumps(
            {
                "complete": result.get("complete", False),
                "coverage": result.get("coverage", {}),
            }
        )
    )
