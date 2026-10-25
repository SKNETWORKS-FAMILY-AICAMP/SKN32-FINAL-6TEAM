"""Zero-credential pinned HTTPS transport; config bounds all reads. No redirects."""

import http.client
import json
import socket
import re
import threading
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from ...components.intake import social_links


class WebFailure(ValueError):
    """Only stable non-sensitive reason codes cross this boundary."""


def checked_url(url, hosts, limits, *, search=False):
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
            p.scheme != "https"
            or p.username is not None
            or p.password is not None
            or p.port not in (None, 443)
        ):
            raise WebFailure("invalid_url")
        if p.hostname not in hosts or p.fragment or (p.query and not search):
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


class PublicWebTransport:
    def __init__(self, limits):
        self.limits = limits
        self.state = threading.local()

    def _wire(self, url, hosts):
        p = checked_url(url, hosts, self.limits, search=True)
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
        c = social_links._PinnedHTTPSConnection(
            p.hostname, addresses[0], timeout=remaining
        )

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
                raise WebFailure(
                    "redirect_blocked"
                    if 300 <= r.status < 400
                    else "http_" + str(r.status)
                )
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
            text = raw.decode("utf-8", errors="strict")
            return json.loads(text) if kind == "application/json" else text
        finally:
            timer.cancel()
            c.close()

    def __call__(self, url, hosts, *, allow=lambda: False):
        try:
            p = checked_url(url, hosts, self.limits, search=True)
            if not allow():
                raise WebFailure("budget_blocked")
            robots = self._wire("https://" + p.hostname + "/robots.txt", hosts)
            if not isinstance(robots, str):
                raise WebFailure("robots_unreadable")
            policy = RobotFileParser()
            policy.parse(robots.splitlines())
            if (not policy.can_fetch("triPilot-public-facts", url)
                    or not _wildcard_robots_allowed(robots, url)):
                raise WebFailure("robots_blocked")
            if not allow():
                raise WebFailure("budget_blocked")
            return self._wire(url, hosts)
        except social_links.MetadataError as e:
            raise WebFailure(e.code) from None
        except TimeoutError:
            raise WebFailure("web_timeout") from None
        except (OSError, http.client.HTTPException, UnicodeError, ValueError) as e:
            if isinstance(e, WebFailure):
                raise
            raise WebFailure("transport_or_body_error") from None
