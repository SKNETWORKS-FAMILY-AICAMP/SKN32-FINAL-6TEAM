"""Explicit Activity-only public lookup: search discovers, official JSON-LD supplies facts.

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
from urllib.parse import urlencode

from ...instances.activity.place_aliases import key_of
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

    def read(self, url, hosts, *, search=False):
        checked_url(url, hosts, self.limits, search=search)
        if self._limiter is None:
            raise WebFailure("budget_unconfigured")
        try:
            if isinstance(self.fetch, PublicWebTransport):
                return self.fetch(url, hosts, allow=self._allow)
            if not self._allow():
                raise WebFailure("budget_blocked")
            return self.fetch(url, hosts)
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


class OfficialSourceExtract(_PublicSource):
    name = "activity_official_extract"

    def extract(self, url, identity, *, tolerance):
        params = {
            "identity": json.dumps(identity, sort_keys=True),
            "tolerance": tolerance,
        }
        cached = self._from_cache(url, params)
        if cached is not None:
            return cached
        body = self.read(url, identity["official_hosts"])
        if not isinstance(body, str):
            raise WebFailure("page_unreadable")
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
                "applies_on": None,
                "checked_at": datetime.now(UTC).isoformat(),
                "confidence": "official_structured",
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }
        if facts:
            self._remember(url, params, facts)
        return facts


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
            urls = self.search.discover(identity, self.config)
            facts = {}
            failures = []
            for url in list(dict.fromkeys(urls))[: self.config["max_pages"]]:
                if time.monotonic() >= deadline:
                    raise WebFailure("web_timeout")
                try:
                    checked_url(url, identity["official_hosts"], self.limits)
                    extracted = self.extract.extract(
                        url, identity, tolerance=self.config["coordinate_tolerance"]
                    )
                except WebFailure as exc:
                    failures.append(str(exc))
                    continue
                for field, fact in extracted.items():
                    if field in facts and facts[field]["value"] != fact["value"]:
                        raise WebFailure("conflicting_sources")
                    facts[field] = fact
            for reason in (
                "address_mismatch",
                "coordinate_mismatch",
                "ambiguous_identity",
            ):
                if reason in failures:
                    raise WebFailure(reason)
            if not facts:
                # Report the first official-page read failure (robots/redirect/403/identity) ahead of
                # URLs skipped by the official-host filter, so the real blocker stays visible.
                read = [f for f in failures if f not in ("source_url_rejected", "invalid_url")]
                raise WebFailure((read or failures or ["no_official_facts"])[0])
            return {
                **base,
                "reason": "date_specific_unverified",
                "identity_verified": True,
                "canonical_id": identity["canonical_id"],
                "facts": facts,
                "checked_at": min(f["checked_at"] for f in facts.values()),
                "confidence": "official_structured",
                "search_backend": self.config.get("backend"),
                "unknown": ["closed_days", "date_specific"],
                "source_failures": failures,
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
