"""Customer-visible extraction and URL/network trust boundaries for SNS dining links."""
from __future__ import annotations

import hashlib
import importlib
import threading
from urllib.parse import urlsplit

import pytest


@pytest.fixture
def api():
    return importlib.import_module("app.domains.travel_ops.components.intake.social_links")


@pytest.fixture
def limits():
    return {
        "max_links": 10, "max_url_chars": 2048, "timeout_seconds": 8,
        "max_response_bytes": 4096, "max_redirects": 3, "max_metadata_chars": 600,
        "max_restaurants_per_link": 5, "max_preview_pairs": 40,
        "allowed_hosts": [
            "instagram.com", "www.instagram.com", "m.instagram.com",
            "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
            "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
        ],
    }


STAMP = "2026-10-15T01:02:03+00:00"
VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
POST = "https://www.instagram.com/p/cafe123/"
TEXT = "서울 서촌의 토속촌 본점에서 삼계탕을 먹었습니다."


class Chat:
    def __init__(self, restaurants=None, *, error=None, raw=None):
        self.restaurants = restaurants
        self.error = error
        self.raw = raw
        self.prompts = []

    def json(self, system, user):
        self.prompts.append((system, user))
        if self.error:
            raise self.error
        return self.raw if self.raw is not None else {"restaurants": self.restaurants or []}


def restaurant(name="토속촌", *, source="metadata", quote=TEXT, **fields):
    return {"name": name, "area": None, "branch": None, "menu": None,
            "evidence": [{"source": source, "quote": quote}], **fields}


def metadata(url, *, limits):
    return {"text": TEXT, "canonical_url": url, "checked_at": STAMP}


@pytest.mark.parametrize("urls,canonical", [
    (["https://youtu.be/dQw4w9WgXcQ?si=share", VIDEO,
      "https://m.youtube.com/shorts/dQw4w9WgXcQ#t=10"], VIDEO),
    (["https://instagram.com/reel/cafe123/?igsh=tracking",
      "https://www.instagram.com/reels/cafe123/"],
     "https://www.instagram.com/reel/cafe123/"),
    # [2026-10-15 실링크] 계정 이름이 든 게시물 주소(공유 · 계정 화면에서 열린 주소)도 같은 게시물이다
    (["https://www.instagram.com/seoul_thehotple/p/DeayvzLk3_Y/?img_index=1",
      "https://www.instagram.com/p/DeayvzLk3_Y/"],
     "https://www.instagram.com/p/DeayvzLk3_Y/"),
    (["https://www.instagram.com/some.user_1/reel/cafe456/", "https://www.instagram.com/reel/cafe456/"],
     "https://www.instagram.com/reel/cafe456/"),
    (["https://www.tiktok.com/@food/video/123456?is_from_webapp=1",
      "https://www.tiktok.com/@another/video/123456"],
     "https://www.tiktok.com/@food/video/123456"),
])
def test_post_aliases_merge_without_losing_original_sources(api, limits, urls, canonical):
    result = api.resolve_links([{"url": url} for url in urls], chat=Chat([restaurant()]),
                               fetch=metadata, limits=limits)
    assert len(result) == 1
    assert result[0]["source_urls"] == urls
    assert result[0]["status"] == "identified"
    assert result[0]["restaurants"][0]["evidence"][0]["source_url"] == canonical


def test_duplicate_priority_uses_must_without_turning_it_into_a_schedule_lock(api, limits):
    result = api.resolve_links([{"url": VIDEO}, {"url": VIDEO, "priority": "must"}],
                               chat=Chat([restaurant()]), fetch=metadata, limits=limits)
    assert result[0]["priority"] == "must"
    assert "customer_pinned" not in result[0]


@pytest.mark.parametrize("url", [
    "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com@127.0.0.1/watch?v=dQw4w9WgXcQ",
    "https://user:password@www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
    "https://127.0.0.1/", "https://[::1]/", "file:///etc/passwd",
    "https://www.youtube.com/%2e%2e/watch?v=dQw4w9WgXcQ",
])
def test_unsafe_urls_are_explicit_results_without_fetching(api, limits, url):
    def forbidden_fetch(*args, **kwargs):
        pytest.fail("unsafe URL reached the network boundary")

    result = api.resolve_links([{"url": url}], fetch=forbidden_fetch, limits=limits)
    assert result[0]["status"] in {"invalid", "unsupported"}
    assert result[0]["source_urls"] == [url]
    assert result[0]["restaurants"] == []


def test_profiles_and_unknown_platforms_do_not_masquerade_as_supported_posts(api, limits):
    result = api.resolve_links([{"url": "https://www.instagram.com/tasty/"},
                                {"url": "https://example.com/food"}], fetch=metadata, limits=limits)
    assert [row["status"] for row in result] == ["unsupported", "unsupported"]


def test_over_limit_inputs_remain_visible_but_are_not_read(api, limits):
    result = api.resolve_links([{"url": VIDEO}, {"url": POST}], fetch=metadata,
                               chat=Chat(), limits={**limits, "max_links": 1})
    assert len(result) == 2
    assert result[1]["reason"] == "link_limit_exceeded"
    assert result[1]["source_urls"] == [POST]


def test_too_long_url_remains_an_explicit_invalid_result(api, limits):
    result = api.resolve_links([{"url": VIDEO}], fetch=metadata,
                               limits={**limits, "max_url_chars": 15})
    assert result[0]["reason"] == "url_too_long"


def test_verified_fields_and_prompt_identity_are_attached_to_exact_quote(api, limits):
    chat = Chat([restaurant(area="서울 서촌", branch="본점", menu="삼계탕")])
    result = api.resolve_links([{"url": VIDEO}], chat=chat, fetch=metadata, limits=limits)[0]
    assert result["restaurants"][0]["name"] == "토속촌"
    evidence = result["restaurants"][0]["evidence"][0]
    assert evidence["quote"] == TEXT
    assert evidence["checked_at"] == STAMP
    assert evidence["prompt_version"]
    assert evidence["prompt_hash"] == hashlib.sha256(chat.prompts[0][0].encode()).hexdigest()
    assert "text" not in result


@pytest.mark.parametrize("entry", [
    restaurant(quote="원문에 없는 식당 소개"),
    restaurant(name="가짜식당"),
    restaurant(branch="강남점"),
    restaurant(area="부산"),
    restaurant(menu="초밥"),
    restaurant(source="customer_note"),
])
def test_invented_names_branches_and_unread_quotes_never_become_identified(api, limits, entry):
    result = api.resolve_links([{"url": VIDEO}], chat=Chat([entry]), fetch=metadata, limits=limits)[0]
    assert result["status"] == "failed"
    assert result["reason"] == "evidence_invalid"
    assert result["restaurants"] == []


def test_a_post_with_multiple_restaurants_requires_customer_choice(api, limits):
    text = "서울 토속촌과 서울 금용문을 소개합니다."

    def fetch(url, *, limits):
        return {"text": text, "canonical_url": url, "checked_at": STAMP}

    result = api.resolve_links([{"url": VIDEO}], chat=Chat([
        restaurant(quote=text), restaurant("금용문", quote=text)]), fetch=fetch, limits=limits)[0]
    assert result["status"] == "needs_choice"
    assert [item["name"] for item in result["restaurants"]] == ["토속촌", "금용문"]


def test_unreadable_post_uses_customer_note_but_keeps_source_failure_visible(api, limits):
    def inaccessible(url, *, limits):
        raise OSError("login required; do not expose this raw error")

    note = "서울 서촌 토속촌 본점"
    result = api.resolve_links([{"url": VIDEO, "note": note}],
                               chat=Chat([restaurant(source="customer_note", quote=note)]),
                               fetch=inaccessible, limits=limits)[0]
    assert result["status"] == "identified"
    assert result["reason"] == "source_unavailable_customer_note"
    assert result["source_failure"]
    assert result["restaurants"][0]["evidence"][0]["source"] == "customer_note"


def test_one_source_failure_does_not_erase_other_links(api, limits):
    def fetch(url, *, limits):
        if urlsplit(url).hostname == "www.instagram.com":
            raise TimeoutError("private diagnostic")
        return metadata(url, limits=limits)

    result = api.resolve_links([{"url": POST}, {"url": VIDEO}], chat=Chat([restaurant()]),
                               fetch=fetch, limits=limits)
    assert [item["status"] for item in result] == ["inaccessible", "identified"]
    assert "private diagnostic" not in str(result)


@pytest.mark.parametrize("chat,status,reason", [
    (None, "needs_info", "model_unavailable"),
    (Chat(error=RuntimeError("secret model endpoint")), "failed", "model_failed"),
    (Chat(raw={"wrong": []}), "failed", "model_invalid_output"),
    (Chat([]), "needs_info", "restaurant_not_found"),
])
def test_model_failure_is_distinct_from_missing_restaurant_information(api, limits, chat, status, reason):
    result = api.resolve_links([{"url": VIDEO}], chat=chat, fetch=metadata, limits=limits)[0]
    assert (result["status"], result["reason"]) == (status, reason)
    assert "secret model endpoint" not in str(result)


def test_metadata_limit_prevents_model_from_citing_unread_tail(api, limits):
    def fetch(url, *, limits):
        return {"text": "x" * 40 + TEXT, "canonical_url": url, "checked_at": STAMP}

    result = api.resolve_links([{"url": VIDEO}], chat=Chat([restaurant()]), fetch=fetch,
                               limits={**limits, "max_metadata_chars": 40})[0]
    assert result["reason"] == "evidence_invalid"


def test_canonical_short_link_alias_merges_with_already_supplied_post(api, limits):
    short = "https://vm.tiktok.com/Zfood123/"
    full = "https://www.tiktok.com/@food/video/123456"

    def fetch(url, *, limits):
        return {"text": TEXT, "canonical_url": full, "checked_at": STAMP}

    result = api.resolve_links([{"url": short}, {"url": full}], chat=Chat([restaurant()]),
                               fetch=fetch, limits=limits)
    assert len(result) == 1
    assert result[0]["source_urls"] == [short, full]


def public_dns(host, port, **kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


def test_redirect_to_private_or_unlisted_host_is_blocked_before_following(api, limits, monkeypatch):
    monkeypatch.setattr(api.socket, "getaddrinfo", public_dns)

    def request(url, addresses, *, limits):
        if url != VIDEO:
            pytest.fail("unsafe redirect was followed")
        return 302, {"location": "https://127.0.0.1/admin"}, b""

    monkeypatch.setattr(api, "_request", request)
    with pytest.raises(api.MetadataError, match="unsupported_host"):
        api.fetch_metadata(VIDEO, limits=limits)


def test_mixed_public_and_private_dns_is_rejected(api, limits, monkeypatch):
    def dns(host, port, **kwargs):
        return public_dns(host, port) + [(2, 1, 6, "", ("10.0.0.4", port))]

    monkeypatch.setattr(api.socket, "getaddrinfo", dns)
    with pytest.raises(api.MetadataError, match="private_destination"):
        api.fetch_metadata(VIDEO, limits=limits)


def test_every_redirect_rechecks_dns_before_reading(api, limits, monkeypatch):
    def dns(host, port, **kwargs):
        address = "127.0.0.1" if host == "www.youtube.com" else "93.184.216.34"
        return [(2, 1, 6, "", (address, port))]

    monkeypatch.setattr(api.socket, "getaddrinfo", dns)
    monkeypatch.setattr(api, "_request", lambda *a, **kw: (
        302, {"location": VIDEO}, b""))
    with pytest.raises(api.MetadataError, match="private_destination"):
        api.fetch_metadata("https://youtu.be/dQw4w9WgXcQ", limits=limits)


def test_redirect_count_is_bounded(api, limits, monkeypatch):
    monkeypatch.setattr(api.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(api, "_request", lambda *a, **kw: (
        302, {"location": VIDEO}, b""))
    with pytest.raises(api.MetadataError, match="redirect_limit"):
        api.fetch_metadata(VIDEO, limits={**limits, "max_redirects": 1})


def test_html_metadata_is_read_without_running_or_returning_scripts(api, limits, monkeypatch):
    monkeypatch.setattr(api.socket, "getaddrinfo", public_dns)
    body = ('<title>맛집 소개</title><meta property="og:description" content="서울 토속촌">'
            '<script>토속촌 강남점<script-instruction></script>').encode()
    monkeypatch.setattr(api, "_request", lambda *a, **kw: (
        200, {"content-type": "text/html; charset=utf-8"}, body))
    got = api.fetch_metadata(VIDEO, limits=limits)
    assert "서울 토속촌" in got["text"]
    assert "강남점" not in got["text"]
    assert got["canonical_url"] == VIDEO
    assert got["checked_at"]


def test_non_text_response_is_not_downloaded_as_metadata(api, limits, monkeypatch):
    monkeypatch.setattr(api.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(api, "_request", lambda *a, **kw: (
        200, {"content-type": "video/mp4"}, b"not a video download"))
    with pytest.raises(api.MetadataError, match="unsupported_content_type"):
        api.fetch_metadata(VIDEO, limits=limits)


def test_oversize_response_is_rejected_at_network_read_boundary(api, limits, monkeypatch):
    class Response:
        status = 200

        def getheaders(self):
            return [("content-type", "text/html")]

        def read1(self, amount):
            return b"x" * amount

    class Connection:
        sock = None

        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(api, "_PinnedHTTPSConnection", Connection)
    with pytest.raises(api.MetadataError, match="response_too_large"):
        api._request(VIDEO, ["93.184.216.34"], limits=limits)


def test_html_reading_stops_at_the_head_so_a_large_video_page_still_gives_its_meta_tags(api, limits, monkeypatch):
    # [2026-10-15 실측] A real YouTube watch page is ~1.4MB with og:title near 770KB; only the head is needed.
    head = b"<html><head>" + b"<script>x</script>" * 100 + b'<meta property="og:title" content="Seongsu noodles"></head>'
    body = [head[i:i + 512] for i in range(0, len(head), 512)] + [b"<body>" + b"y" * 4096] * 50
    reads = []

    class Response:
        status = 200

        def getheaders(self):
            return [("content-type", "text/html; charset=utf-8"), ("content-length", str(len(head) + 50 * 4102))]

        def read1(self, amount):
            reads.append(amount)
            return body.pop(0) if body else b""

    class Connection:
        sock = None

        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(api, "_PinnedHTTPSConnection", Connection)
    status, _, got = api._request(VIDEO, ["93.184.216.34"], limits=limits)
    assert status == 200
    assert b"og:title" in got and b"<body>" not in got
    assert len(got) <= limits["max_response_bytes"]
    assert len(body) == 50                  # never read past the head


def test_plain_text_still_rejects_an_announced_oversize_body_before_reading(api, limits, monkeypatch):
    class Response:
        status = 200

        def getheaders(self):
            return [("content-type", "text/plain"), ("content-length", str(limits["max_response_bytes"] + 1))]

        def read1(self, amount):
            raise AssertionError("must not read")

    class Connection:
        sock = None

        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(api, "_PinnedHTTPSConnection", Connection)
    with pytest.raises(api.MetadataError, match="response_too_large"):
        api._request(VIDEO, ["93.184.216.34"], limits=limits)


def test_slow_response_headers_cannot_extend_the_total_request_timeout(api, limits, monkeypatch):
    stopped = threading.Event()

    class Transport:
        def shutdown(self, how):
            stopped.set()

        def close(self):
            stopped.set()

    class Connection:
        sock = Transport()

        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            stopped.wait(0.5)
            raise OSError("socket closed while waiting for headers")

        def close(self):
            stopped.set()

    monkeypatch.setattr(api, "_PinnedHTTPSConnection", Connection)
    with pytest.raises(api.MetadataError, match="source_timeout"):
        api._request(VIDEO, ["93.184.216.34"], limits={**limits, "timeout_seconds": 0.02})


def test_discarded_metadata_tail_is_visible_even_when_a_name_was_extracted(api, limits):
    def fetch(url, *, limits):
        return {"text": TEXT + "x" * 100, "canonical_url": url, "checked_at": STAMP}

    result = api.resolve_links([{"url": VIDEO}], chat=Chat([restaurant()]), fetch=fetch,
                               limits={**limits, "max_metadata_chars": len(TEXT)})[0]
    assert result["status"] == "identified"
    assert "metadata_truncated" in result["omissions"]


def test_discarded_customer_note_tail_is_visible(api, limits):
    note = "토속촌 " + "x" * 100
    result = api.resolve_links([{"url": VIDEO, "note": note}], chat=Chat(), fetch=metadata,
                               limits={**limits, "max_metadata_chars": 20})[0]
    assert "customer_note_truncated" in result["omissions"]


@pytest.mark.parametrize("source", [[], {}])
def test_malformed_model_evidence_is_reported_without_aborting_the_batch(api, limits, source):
    result = api.resolve_links([{"url": VIDEO}],
                               chat=Chat([restaurant(source=source)]), fetch=metadata, limits=limits)[0]
    assert result["status"] == "failed"
    assert result["reason"] == "evidence_invalid"
