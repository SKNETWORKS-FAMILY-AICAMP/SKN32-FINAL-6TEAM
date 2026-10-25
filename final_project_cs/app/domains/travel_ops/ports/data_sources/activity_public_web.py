"""Explicit Activity-only public lookup: search discovers, official pages supply facts.

Facts come from official JSON-LD and, when `official_text` is configured, from hours/closure
sentences in the official page body read by the rule parser `official_hours_text` (no model).
No model, customer text, keys, cookies, booking or itinerary input is accepted.
Operational enablement requires reviewed public identities and separate free-search config.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit

from ...instances.activity.place_aliases import key_of
from . import official_hours_text
from .base import TravelSource
from .public_web_transport import (
    PublicWebTransport,
    WebFailure,
    checked_url,
    social_links,
)

__all__ = [
    "ActivityPublicWeb",
    "DdgsWebSearch",
    "OfficialSourceExtract",
    "PublicWebSearch",
    "PublicWebTransport",
    "WebFailure",
    "build_activity_public_web",
    "social_links",
]


class _JsonLD(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.chunks = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if (
            tag == "script"
            and dict(attrs).get("type", "").lower() == "application/ld+json"
        ):
            self.active = True
            self.chunks = []

    def handle_data(self, data):
        if self.active:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            try:
                value = json.loads("".join(self.chunks))
                self.blocks.extend(value if isinstance(value, list) else [value])
            except ValueError:
                pass
            self.active = False


class _PublicSource(TravelSource):
    def __init__(self, *, limits, limiter, cache, fetch):
        super().__init__(
            timeout=limits["timeout_seconds"], limiter=limiter, cache=cache
        )
        self.fetch = fetch
        self.limits = limits

    def read(self, url, hosts, *, search=False, bounds=None):
        """`bounds` (official pages only): redirects/http_ok/subdomains opted in by config."""
        bounds = bounds or {}
        # Opted-in official reads accept a query string (e.g. `.do?menuNo=`): it comes from the
        # reviewed homepage or the official page itself, never from customer text.
        checked_url(url, hosts, self.limits, search=search or bool(bounds),
                    http_ok=bounds.get("http_ok", False), subdomains=bounds.get("subdomains", False))
        if self._limiter is None:
            raise WebFailure("budget_unconfigured")
        try:
            if isinstance(self.fetch, PublicWebTransport):
                return self.fetch(url, hosts, allow=self._allow, **bounds)
            if not self._allow():
                raise WebFailure("budget_blocked")
            return self.fetch(url, hosts, **bounds)
        except WebFailure as exc:
            prefix = "search_" if self.name == "activity_web_search" else "extract_"
            self._miss(str(exc))
            raise WebFailure(prefix + str(exc)) from None


class PublicWebSearch(_PublicSource):
    name = "activity_web_search"

    def discover(self, identity, config):
        # Never pass the original customer label, snippets or other customer fields.
        url = (
            config["search_endpoint"]
            + "?"
            + urlencode(
                {"q": identity["name"] + (" 공식" if config.get("query_style") == "official"
                                          else " " + identity["address"]), "format": "json"}
            )
        )
        checked_url(config["search_endpoint"], config["search_hosts"], self.limits)
        cached = self._from_cache(url, {})
        if cached is not None:
            return cached
        body = self.read(url, config["search_hosts"], search=True)
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("results"), list)
            or body.get("error")
        ):
            raise WebFailure("search_failed")
        urls = [
            row["url"]
            for row in body["results"]
            if isinstance(row, dict) and isinstance(row.get("url"), str)
        ]
        self._remember(url, {}, urls)
        return urls


def _ddgs_engine_hosts(backends):
    """Hosts the configured ddgs text engines contact, read from the installed ddgs registry.

    ImportError means the pinned package is absent; KeyError means an unknown engine name.
    """
    from urllib.parse import urlsplit

    from ddgs.engines import ENGINES

    return {urlsplit(ENGINES["text"][name].search_url).hostname for name in backends}


def _ddgs_client_factory():
    """`timeout -> client` with `.text(query, **options)`; never reads an ambient proxy."""
    from ddgs import DDGS

    return lambda timeout: DDGS(proxy=None, timeout=timeout)


# ddgs exception class name -> stable reason (library errors only, never customer text).
_DDGS_ERRORS = {"RatelimitException": "http_429", "TimeoutException": "web_timeout"}


class DdgsWebSearch(TravelSource):
    """Free keyless discovery through ddgs (unofficial search-result collection).

    Results only nominate URLs; titles/snippets are dropped here. Same meter, cache, deadline
    and official-host rules as the SearXNG backend; failures surface as `search_*` reasons.
    """

    name = "activity_web_search"

    def __init__(self, *, limits, limiter, cache, client):
        super().__init__(timeout=limits["timeout_seconds"], limiter=limiter, cache=cache)
        self.limits = limits
        self.client = client
        self.deadline = None

    def _fail(self, code):
        self._miss(code)
        raise WebFailure("search_" + code)

    def discover(self, identity, config):
        options = config["ddgs"]
        district = identity.get("district")
        if not isinstance(district, str) or not district.strip():
            raise WebFailure("search_query_unconfigured")
        # Public canonical name + administrative district only; never the customer's label/address.
        query = identity["name"] + " " + district.strip()
        backend = ",".join(options["backends"])
        params = {"backend": backend, "region": options["region"],
                  "safesearch": options["safesearch"], "max_results": options["max_results"]}
        cached = self._from_cache("ddgs:" + query, params)
        if cached is not None:
            return cached
        if self._limiter is None:
            raise WebFailure("search_budget_unconfigured")
        if os.environ.get("DDGS_PROXY"):
            self._fail("proxy_rejected")
        # One meter unit per engine request so the shared daily budget counts real egress.
        for _ in options["backends"]:
            if not self._allow():
                self._fail("budget_blocked")
        deadline = self.deadline if self.deadline is not None else time.monotonic() + self.limits["timeout_seconds"]
        remaining = min(self.limits["timeout_seconds"], deadline - time.monotonic())
        if remaining < 1:
            self._fail("web_timeout")
        try:
            hits = self.client(int(remaining)).text(query, **params)
        except Exception as exc:  # noqa: BLE001 - bounded to the ddgs call; mapped to stable codes
            code = _DDGS_ERRORS.get(type(exc).__name__)
            if code is None:
                code = "no_results" if "no results" in str(exc).lower() else "failed"
            self._fail(code)
        if time.monotonic() > deadline:
            self._fail("web_timeout")
        if not isinstance(hits, list):
            self._fail("failed")
        urls = [h["href"] for h in hits if isinstance(h, dict) and isinstance(h.get("href"), str)]
        if not urls:
            self._fail("no_results")
        self._remember("ddgs:" + query, params, urls)
        return urls


def official_bounds(config):
    """Opt-in widening for official pages only (search reads never get these)."""
    redirects = config.get("official_max_redirects") or 0
    if not config.get("official_http") and not redirects:
        return {}
    return {"redirects": int(redirects), "http_ok": config.get("official_http") is True, "subdomains": True}


def _text_fact(body, url, identity):
    """Hours/closure sentences from the official page body (rule parser), or a stable reason."""
    text, links = official_hours_text.visible(body)
    names = [key_of(n) for n in [identity["name"], *identity.get("aliases", [])]]
    if not any(n and n in key_of(text) for n in names):
        raise WebFailure("identity_unverified")
    parsed = official_hours_text.parse(text)
    if "ambiguous" in parsed:
        if parsed["ambiguous"] != "no_hours":
            # An official page whose hours this grammar cannot pin down makes the place unknown,
            # even if another official page reads cleanly (no cherry-picking the readable one).
            raise WebFailure("ambiguous_hours")
        return None, links, parsed["ambiguous"]
    # Server-side position check: every quote must be a verbatim span of this page's text.
    if not parsed["quotes"] or any(text.find(q) < 0 for q in parsed["quotes"]):
        raise WebFailure("quote_unverified")
    value = {k: parsed[k] for k in ("hours", "closed", "open_all_year")}
    return value, links, [{"quote": q, "offset": text.find(q)} for q in parsed["quotes"]]


class OfficialSourceExtract(_PublicSource):
    name = "activity_official_extract"

    def extract(self, url, identity, *, tolerance, config=None):
        return self.extract_page(url, identity, tolerance=tolerance, config=config)[0]

    def extract_page(self, url, identity, *, tolerance, config=None):
        """(facts, same-official guide links). Links are only nominated, never trusted as facts."""
        config = config or {}
        bounds = official_bounds(config)
        params = {
            "identity": json.dumps(identity, sort_keys=True),
            "tolerance": tolerance,
            **({"text": True, **bounds} if config.get("official_text") else {}),
        }
        cached = self._from_cache(url, params)
        if cached is not None:
            return cached, []
        body = self.read(url, identity["official_hosts"], bounds=bounds)
        if not isinstance(body, str):
            raise WebFailure("page_unreadable")
        final = getattr(body, "url", "") or url
        if config.get("official_text"):
            jsonld = _JsonLD()
            jsonld.feed(body)
            if not any(isinstance(n, dict) and "openingHours" in str(n) for n in jsonld.blocks):
                return self._text_page(body, final, url, identity, params)
        parser = _JsonLD()
        parser.feed(body)
        nodes = []
        for node in parser.blocks:
            if isinstance(node, dict):
                nodes.extend(node.get("@graph", [node]))
        matches = []
        aliases = {key_of(n) for n in [identity["name"], *identity.get("aliases", [])]}
        for node in nodes:
            if (
                not isinstance(node, dict)
                or key_of(str(node.get("name", ""))) not in aliases
            ):
                continue
            address = node.get("address")
            if isinstance(address, dict):
                address = " ".join(
                    str(address.get(k) or "")
                    for k in ("addressRegion", "addressLocality", "streetAddress")
                ).strip()
            if key_of(str(address or "")) != key_of(identity["address"]):
                raise WebFailure("address_mismatch")
            if identity.get("coordinates") is not None:
                try:
                    geo = node.get("geo") or {}
                    actual = [float(geo["latitude"]), float(geo["longitude"])]
                    if not all(math.isfinite(a) for a in actual):
                        raise WebFailure("coordinates_unverified")
                    if any(
                        abs(a - float(b)) > tolerance
                        for a, b in zip(actual, identity["coordinates"], strict=True)
                    ):
                        raise WebFailure("coordinate_mismatch")
                except (ValueError, KeyError, TypeError) as exc:
                    if isinstance(exc, WebFailure):
                        raise
                    raise WebFailure("coordinates_unverified") from None
            matches.append(node)
        if len(matches) != 1:
            raise WebFailure("ambiguous_identity" if matches else "identity_unverified")
        node = matches[0]
        facts = {}
        value = node.get("openingHours")
        # Strict structured schedule syntax only, never interpret arbitrary prose.
        hhmm = r"(?:[01]\d|2[0-3]):[0-5]\d"
        days = r"(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:[-,](?:Mo|Tu|We|Th|Fr|Sa|Su))*"
        if isinstance(value, str) and re.fullmatch(
            r"(?:" + days + r"\s+)?" + hhmm + r"(?:-" + hhmm + r")?", value
        ):
            facts["business_hours"] = {
                "value": value,
                "source_url": url,
                "format": "jsonld",
                "field": "openingHours",
                "source_kind": "official_homepage",
                "applies_on": None,
                "checked_at": datetime.now(UTC).isoformat(),
                "confidence": "official_structured",
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }
        if facts:
            self._remember(url, params, facts)
        return facts, []

    def _text_page(self, body, final, url, identity, params):
        value, links, detail = _text_fact(body, final, identity)
        if value is None:
            return {}, links
        facts = {"business_hours": {
            "value": value,
            "quotes": detail,
            "source_url": final,
            "scheme": urlsplit(final).scheme,
            "source_kind": "official_homepage",
            "evidence": "text",
            "checked_at": datetime.now(UTC).isoformat(),
            "confidence": "official_text",
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        }}
        self._remember(url, params, facts)
        return facts, links


def _merge_hours(old, new):
    """Same hours from two official pages may differ only by one page omitting closures."""
    a, b = old["value"], new["value"]
    if old.get("evidence") != new.get("evidence"):
        raise WebFailure("conflicting_sources")
    if old.get("evidence") != "text":
        if a != b:
            raise WebFailure("conflicting_sources")
        return old
    if a["hours"] != b["hours"]:
        raise WebFailure("conflicting_sources")
    closed = sorted(set(a["closed"]) | set(b["closed"]), key=official_hours_text.DAYS.index)
    open_all_year = a["open_all_year"] or b["open_all_year"]
    if open_all_year and closed:
        raise WebFailure("conflicting_sources")
    return {**old, "value": {**a, "closed": closed, "open_all_year": open_all_year},
            "quotes": old["quotes"] + [q for q in new["quotes"] if q not in old["quotes"]],
            "also_source_url": new["source_url"]}


_GUIDE_LINK = official_hours_text.GUIDE_LINK


class ActivityPublicWeb:
    def __init__(self, config, *, limits, limiter, cache, fetch=None, ddgs_client=None):
        self.config = config or {}
        self.limits = limits
        if not self.config.get("enabled"):
            return
        fetch = fetch or PublicWebTransport(limits)
        if self.config.get("backend") == "ddgs":
            self.search = DdgsWebSearch(
                limits=limits, limiter=limiter, cache=cache, client=ddgs_client
            )
        else:
            self.search = PublicWebSearch(
                limits=limits, limiter=limiter, cache=cache, fetch=fetch
            )
        self.extract = OfficialSourceExtract(
            limits=limits, limiter=limiter, cache=cache, fetch=fetch
        )
        self.lock = threading.Lock()

    def lookup(self, name):
        base = {
            "status": "unknown",
            "via": "public_web",
            "needs_question": True,
            "confidence": "unknown",
            "facts": {},
            "unknown": ["business_hours", "closed_days", "date_specific"],
        }
        if not self.config.get("enabled"):
            detail = self.config.get("config_detail")
            return {**base, "reason": "web_not_configured", **({"config_detail": detail} if detail else {})}
        if not self.lock.acquire(timeout=self.config["total_seconds"]):
            return {**base, "reason": "web_busy"}
        try:
            deadline = time.monotonic() + self.config["total_seconds"]
            for source in (self.search, self.extract):
                if isinstance(getattr(source, "fetch", None), PublicWebTransport):
                    source.fetch.state.deadline = deadline
            if isinstance(self.search, DdgsWebSearch):
                self.search.deadline = deadline
            matches = [
                i
                for i in self.config.get("identities", [])
                if key_of(name)
                in {key_of(i["name"]), *(key_of(a) for a in i.get("aliases", []))}
            ]
            if len(matches) != 1:
                raise WebFailure(
                    "ambiguous_identity" if matches else "identity_unverified"
                )
            identity = matches[0]
            if identity.get("provenance") != "public_catalog":
                raise WebFailure("provenance_rejected")
            bounds = official_bounds(self.config)
            homepage = identity.get("homepage") if self.config.get("official_text") else None
            search_failure = None
            try:
                urls = self.search.discover(identity, self.config)
            except WebFailure as exc:
                # The reviewed homepage is still an official seed; without one, search failure ends here.
                if not homepage:
                    raise
                urls, search_failure = [], str(exc)
            # Reviewed homepage first, then search nominations; guide links found on official
            # pages join the same queue. Every URL re-passes the official host/scheme bounds.
            queue = list(dict.fromkeys(([homepage] if homepage else []) + list(urls)))
            seen, pages = set(), 0
            facts = {}
            failures = []
            while queue and pages < self.config["max_pages"]:
                url = queue.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                if time.monotonic() >= deadline:
                    raise WebFailure("web_timeout")
                try:
                    checked_url(url, identity["official_hosts"], self.limits, search=bool(bounds),
                                http_ok=bounds.get("http_ok", False), subdomains=bool(bounds))
                    pages += 1
                    extracted, links = self.extract.extract_page(
                        url, identity, tolerance=self.config["coordinate_tolerance"], config=self.config
                    )
                except WebFailure as exc:
                    failures.append(str(exc))
                    continue
                for href, label in links:
                    if not _GUIDE_LINK.search(label or ""):
                        continue
                    nominated = urljoin(url, href).split("#", 1)[0]
                    try:
                        checked_url(nominated, identity["official_hosts"], self.limits, search=True,
                                    http_ok=bounds.get("http_ok", False), subdomains=bool(bounds))
                    except WebFailure:
                        continue
                    if nominated not in seen and nominated not in queue:
                        queue.append(nominated)
                for field, fact in extracted.items():
                    facts[field] = _merge_hours(facts[field], fact) if field in facts else fact
            for reason in (
                "address_mismatch",
                "coordinate_mismatch",
                "ambiguous_identity",
                "extract_ambiguous_hours",
                "ambiguous_hours",
            ):
                if reason in failures:
                    raise WebFailure(reason)
            if not facts:
                # Report the first official-page read failure (robots/redirect/403/identity) ahead of
                # URLs skipped by the official-host filter, so the real blocker stays visible.
                read = [f for f in failures if f not in ("source_url_rejected", "invalid_url")]
                if search_failure:
                    failures.append(search_failure)
                raise WebFailure((read or failures or ["no_official_facts"])[0])
            text = any(f.get("evidence") == "text" for f in facts.values())
            hours = facts.get("business_hours", {}).get("value")
            known_closed = text and isinstance(hours, dict) and (hours["closed"] or hours["open_all_year"])
            return {
                **base,
                "reason": "date_specific_unverified",
                "identity_verified": True,
                "canonical_id": identity["canonical_id"],
                "facts": facts,
                "checked_at": min(f["checked_at"] for f in facts.values()),
                "confidence": "official_text" if text else "official_structured",
                "search_backend": self.config.get("backend"),
                "unknown": ["date_specific"] if known_closed else ["closed_days", "date_specific"],
                "source_failures": failures,
                **({"search_failure": search_failure} if search_failure else {}),
            }
        except WebFailure as exc:
            return {**base, "reason": str(exc)}
        except (KeyError, TypeError, ValueError):
            return {**base, "reason": "provider_config_or_body_invalid"}
        finally:
            self.lock.release()


def _ddgs_detail(cfg):
    """None when the ddgs block is bounded and every engine host is allowlisted, else a reason."""
    options = cfg.get("ddgs")
    if not isinstance(options, dict):
        return "ddgs_config_missing"
    backends = options.get("backends")
    if (
        not isinstance(backends, list)
        or not backends
        or not all(isinstance(b, str) and b and b not in ("auto", "all") for b in backends)
    ):
        return "ddgs_backends_unbounded"
    if (
        not isinstance(options.get("region"), str)
        or options.get("safesearch") not in ("on", "moderate", "off")
        or not isinstance(options.get("max_results"), int)
        or isinstance(options.get("max_results"), bool)
        or options["max_results"] <= 0
    ):
        return "ddgs_options_invalid"
    try:
        hosts = _ddgs_engine_hosts(backends)
    except ImportError:
        return "ddgs_package_missing"
    except (KeyError, AttributeError, TypeError):
        return "ddgs_backend_unknown"
    if not hosts or not hosts.issubset(set(cfg.get("search_hosts") or [])):
        return "ddgs_backend_host_unlisted"
    return None


def build_activity_public_web(settings, guardrails, *, limiter, cache):
    """Register through existing TravelSources/guardrails/budget/cache interfaces.

    No new key or paid provider. Missing approval or budget keeps it observable OFF
    (`config_detail` names why). Backends: `searxng` (JSON endpoint) or `ddgs` (keyless
    unofficial search-result collection). No numeric limits are invented: inherit shared
    social HTTP and source config; ddgs options come from `travel.activity_public_web.ddgs`.
    """
    cfg = guardrails.get("travel.activity_public_web") or {}
    if not cfg.get("enabled"):
        return ActivityPublicWeb(
            {"enabled": False}, limits=None, limiter=None, cache=None
        )
    limits = guardrails.get("travel.social_dining")
    names = {"activity_web_search", "activity_official_extract"}
    backend = cfg.get("backend")
    detail = None
    if backend not in ("searxng", "ddgs"):
        detail = "backend_unsupported"
    elif not (
        cfg.get("enabled") is True
        and cfg.get("paid") is False
        and cfg.get("approved_public_queries") is True
    ):
        detail = "not_approved"
    elif not (
        names.issubset(getattr(limiter, "meters", set()))
        and getattr(limiter, "_on_db_error", None) == "refuse"
        and all(
            isinstance((cfg.get("daily_limits") or {}).get(n), int)
            and (cfg.get("daily_limits") or {})[n] > 0
            for n in names
        )
    ):
        detail = "budget_unconfigured"
    else:
        try:
            if backend == "searxng":
                checked_url(cfg["search_endpoint"], cfg["search_hosts"], limits)
            else:
                detail = _ddgs_detail(cfg)
            if detail is None and (
                not cfg["identities"]
                or cfg["max_pages"] <= 0
                or cfg["total_seconds"] <= 0
                or cfg["coordinate_tolerance"] < 0
            ):
                detail = "limits_or_identities_invalid"
        except (KeyError, TypeError, ValueError):
            detail = "config_invalid"
    # Disabled providers do not read numeric config or create network resources.
    if detail is not None:
        return ActivityPublicWeb(
            {"enabled": False, "config_detail": detail}, limits=None, limiter=None, cache=None
        )
    client = _ddgs_client_factory() if backend == "ddgs" else None
    return ActivityPublicWeb(cfg, limits=limits, limiter=limiter, cache=cache, ddgs_client=client)
