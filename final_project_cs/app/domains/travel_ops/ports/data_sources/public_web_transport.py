"""Zero-credential pinned transport; config bounds all reads.

Search reads stay HTTPS-only with no redirects. Official-page reads may opt in (per call) to
plain-HTTP GET and a bounded number of redirects that stay inside the official host set.
"""

import http.client
import json
import socket
import re
import threading
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from ...components.intake import social_links


class WebFailure(ValueError):
    """Only stable non-sensitive reason codes cross this boundary."""


class RedirectFailure(WebFailure):
    """`redirect_blocked` that keeps the Location for a caller allowed to follow it."""

    def __init__(self, location):
        super().__init__("redirect_blocked")
        self.location = location


class Page(str):
    """Decoded official page body that remembers the final URL it was read from."""

    url: str = ""


def host_allowed(host, hosts, *, subdomains=False):
    host = (host or "").lower()
    return host in hosts or (subdomains and any(host.endswith("." + h) for h in hosts))


def checked_url(url, hosts, limits, *, search=False, http_ok=False, subdomains=False):
    if (
        not isinstance(url, str)
        or len(url) > limits["max_url_chars"]
        or any(ord(c) <= 32 for c in url)
        or "\\" in url
    ):
        raise WebFailure("invalid_url")
    try:
        p = urlsplit(url)
        if (
            p.scheme not in (("https", "http") if http_ok else ("https",))
            or p.username is not None
            or p.password is not None
            or p.port not in (None, 443 if p.scheme == "https" else 80)
        ):
            raise WebFailure("invalid_url")
        if not host_allowed(p.hostname, hosts, subdomains=subdomains) or p.fragment or (p.query and not search):
            raise WebFailure("source_url_rejected")
    except ValueError:
        raise WebFailure("source_url_rejected") from None
    return p


def _wildcard_robots_allowed(text, url, agent="triPilot-public-facts"):
    """Apply wildcard/$ rules missing from stdlib RobotFileParser.

    Retain stdlib denial as an additional conservative guard. A successful
    robots fetch alone must not permit SearXNG's /*?*q=* prohibited queries.
    """
    groups = []
    agents, rules = [], []
    for line in [*text.splitlines(), "User-agent: sentinel-end"]:
        field, sep, value = line.split("#", 1)[0].partition(":")
        if not sep:
            continue
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif field in ("allow", "disallow") and agents and value:
            rules.append((field, value))
    selected = [(max((len(a) for a in aa if a != "*" and a in agent.lower()), default=0), aa, rr)
                for aa, rr in groups]
    specificity = max((n for n, _, _ in selected), default=0)
    target = urlsplit(url).path or "/"
    if urlsplit(url).query:
        target += "?" + urlsplit(url).query
    def octets(value):
        # RFC9309: decode unreserved octets, retain encoded reserved separators.
        def normalized(match):
            code = int(match.group()[1:], 16)
            char = chr(code)
            return char if char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~" else f"%{code:02X}"
        return re.sub(r"%[0-9a-fA-F]{2}", normalized, value)

    target = octets(target)
    matches = []
    for n, aa, rr in selected:
        if (specificity and n != specificity) or (not specificity and "*" not in aa):
            continue
        for directive, pattern in rr:
            pattern = octets(pattern)
            terminal = pattern.endswith("$")
            stem = pattern[:-1] if terminal else pattern
            expr = "^" + re.escape(stem).replace(r"\*", ".*") + ("$" if terminal else "")
            if re.search(expr, target):
                matches.append((len(stem.replace("*", "")), directive == "allow"))
    return not matches or max(matches)[1]


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Plain-HTTP GET to an already public-checked address (official pages only, no cookies)."""

    def __init__(self, host, address, *, timeout):
        super().__init__(host, timeout=timeout)
        self._address = address
        self._transport_socket = None

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)
        self._transport_socket = self.sock


_CHARSETS = {"utf-8": "utf-8", "utf8": "utf-8", "euc-kr": "cp949", "cp949": "cp949", "ks_c_5601-1987": "cp949"}


def _decode(raw, content_type):
    """Strict decode by declared charset (header, then <meta>); only UTF-8 and EUC-KR(as CP949)."""
    declared = re.search(r"charset=([\w-]+)", content_type, re.I)
    meta = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4096], re.I)
    names = {n.lower() for n in (declared and declared.group(1),
                                  meta and meta.group(1).decode("ascii", "ignore")) if n}
    codecs = {_CHARSETS.get(n) for n in names}
    if None in codecs or len(codecs) > 1:
        raise WebFailure("charset_unsupported")
    return raw.decode(codecs.pop() if codecs else "utf-8", errors="strict")


class PublicWebTransport:
    def __init__(self, limits):
        self.limits = limits
        self.state = threading.local()

    def _wire(self, url, hosts, *, http_ok=False, subdomains=False):
        p = checked_url(url, hosts, self.limits, search=True, http_ok=http_ok, subdomains=subdomains)
        remaining = min(
            self.limits["timeout_seconds"],
            getattr(
                self.state,
                "deadline",
                time.monotonic() + self.limits["timeout_seconds"],
            )
            - time.monotonic(),
        )
        if remaining <= 0:
            raise WebFailure("web_timeout")
        addresses = social_links._public_addresses(p.hostname, remaining)
        remaining = min(
            remaining,
            getattr(self.state, "deadline", time.monotonic() + remaining)
            - time.monotonic(),
        )
        if remaining <= 0:
            raise WebFailure("web_timeout")
        pinned = social_links._PinnedHTTPSConnection if p.scheme == "https" else _PinnedHTTPConnection
        c = pinned(p.hostname, addresses[0], timeout=remaining)

        def expire():
            sock = getattr(c, "_transport_socket", None) or c.sock
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()

        timer = threading.Timer(remaining, expire)
        timer.daemon = True
        timer.start()
        try:
            target = p.path or "/"
            if p.query:
                target += "?" + p.query
            c.request(
                "GET",
                target,
                headers={
                    "Accept": "text/html,text/plain,application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "triPilot-public-facts/1.0",
                },
            )
            r = c.getresponse()
            if r.status != 200:
                if 300 <= r.status < 400:
                    raise RedirectFailure(r.getheader("Location", ""))
                raise WebFailure("http_" + str(r.status))
            kind = r.getheader("Content-Type", "").split(";")[0].lower()
            if kind not in (
                "text/html",
                "text/plain",
                "application/xhtml+xml",
                "application/json",
            ):
                raise WebFailure("content_type_rejected")
            if r.getheader("Content-Encoding", "identity").lower() != "identity":
                raise WebFailure("encoding_rejected")
            raw = r.read(self.limits["max_response_bytes"] + 1)
            if len(raw) > self.limits["max_response_bytes"]:
                raise WebFailure("body_too_large")
            if kind == "application/json":
                return json.loads(raw.decode("utf-8", errors="strict"))
            return _decode(raw, r.getheader("Content-Type", ""))
        finally:
            timer.cancel()
            c.close()

    def _follow(self, url, hosts, allow, *, redirects, http_ok, subdomains):
        """GET with at most `redirects` hops; every hop re-passes the same host/scheme bounds."""
        for hop in range(redirects + 1):
            try:
                opted = {k: v for k, v in (("http_ok", http_ok), ("subdomains", subdomains)) if v}
                return url, self._wire(url, hosts, **opted)
            except RedirectFailure as exc:
                if hop == redirects:
                    raise WebFailure("redirect_blocked") from None
                try:
                    url = urljoin(url, exc.location)
                    checked_url(url, hosts, self.limits, search=True, http_ok=http_ok, subdomains=subdomains)
                except WebFailure:
                    raise WebFailure("redirect_blocked") from None
                if not allow():
                    raise WebFailure("budget_blocked") from None
        raise WebFailure("redirect_blocked")

    def __call__(self, url, hosts, *, allow=lambda: False, redirects=0, http_ok=False, subdomains=False):
        try:
            bounds = {"redirects": redirects, "http_ok": http_ok, "subdomains": subdomains}
            p = checked_url(url, hosts, self.limits, search=True, http_ok=http_ok, subdomains=subdomains)
            if not allow():
                raise WebFailure("budget_blocked")
            try:
                _, robots = self._follow(p.scheme + "://" + p.hostname + "/robots.txt", hosts, allow, **bounds)
            except WebFailure as exc:
                # RFC 9309 "unavailable" status: an unavailable (404/410) robots.txt allows crawling. Opt-in
                # official readers only; 401/403/429/5xx and network errors still stop the read.
                if not (redirects or http_ok) or str(exc) not in ("http_404", "http_410"):
                    raise
                robots = ""
            if not isinstance(robots, str):
                raise WebFailure("robots_unreadable")
            policy = RobotFileParser()
            policy.parse(robots.splitlines())
            if (not policy.can_fetch("triPilot-public-facts", url)
                    or not _wildcard_robots_allowed(robots, url)):
                raise WebFailure("robots_blocked")
            if not allow():
                raise WebFailure("budget_blocked")
            final, body = self._follow(url, hosts, allow, **bounds)
            if isinstance(body, str):
                body = Page(body)
                body.url = final
            return body
        except social_links.MetadataError as e:
            raise WebFailure(e.code) from None
        except TimeoutError:
            raise WebFailure("web_timeout") from None
        except (OSError, http.client.HTTPException, UnicodeError, ValueError) as e:
            if isinstance(e, WebFailure):
                raise
            raise WebFailure("transport_or_body_error") from None
