"""Ignav MCP 서버(항공 검색·예약 링크)를 확인한다. probe_myrealtrip_mcp 와 같은 모양.

- 주소: https://ignav.com/mcp (Streamable HTTP, mcpservers.org 안내 2026-10-08 확인)
- 키: 환경변수 또는 `.env.apikeys`(커밋 안 함)의 ACOP_IGNAV_API_KEY 를 `X-Api-Key` 헤더로 보낸다. 값은 출력하지 않는다.
- 성공한 요청 1,000건까지 무료, 그 뒤 1,000건당 $2. 검색만 하고 예약·결제는 하지 않는다.
- 응답 원문은 저장하지 않는다. 구조와 몇 항목만 출력한다.

실행 위치: final_project_cs
  python -m scripts.probe_ignav_mcp                               # 도구 목록과 입력 항목
  python -m scripts.probe_ignav_mcp --schema search_flights        # 입력 정의 원문
  python -m scripts.probe_ignav_mcp --call search_flights --arg 이름=값 ... --list 10
값은 숫자·true/false 면 그 형으로, 나머지는 글자로 보낸다. 숫자처럼 생긴 값을 글자로 보내려면 s: 를 붙인다.
"""
from argparse import ArgumentParser
from datetime import datetime
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import platform
import time
from zoneinfo import ZoneInfo

import httpx

URL = "https://ignav.com/mcp"
KEY_NAME = "ACOP_IGNAV_API_KEY"
KEY_FILE = Path(__file__).resolve().parents[1] / ".env.apikeys"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
PROTOCOL = "2025-03-26"


def load_key():
    """환경변수 → .env.apikeys. 값은 출력하지 않는다."""
    value = os.environ.get(KEY_NAME, "").strip()
    if not value and KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            name, sep, raw = line.partition("=")
            if sep and name.strip() == KEY_NAME:
                value = raw.strip().strip('"')
    if not value:
        raise SystemExit(f"{KEY_NAME} 가 비어 있습니다(.env.apikeys 확인)")
    return value


def decode(response):
    """JSON 또는 SSE(text/event-stream) 본문에서 JSON-RPC 메시지들을 꺼낸다."""
    kind = response.headers.get("content-type", "")
    if "text/event-stream" in kind:
        found = []
        for line in response.text.splitlines():
            if line.startswith("data:"):
                try:
                    found.append(json.loads(line[5:].strip()))
                except ValueError:
                    pass
        return found
    try:
        body = response.json()
    except ValueError:
        return []
    return body if isinstance(body, list) else [body]


class Session:
    def __init__(self, client, key):
        self.client, self.key, self.session_id, self.next_id = client, key, None, 0

    def send(self, method, params=None, *, notify=False):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            self.next_id += 1
            message["id"] = self.next_id
        headers = dict(HEADERS)
        headers["X-Api-Key"] = self.key
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        started = time.perf_counter()
        response = self.client.post(URL, json=message, headers=headers)
        took = time.perf_counter() - started
        if response.headers.get("mcp-session-id"):
            self.session_id = response.headers["mcp-session-id"]
        if notify:
            return None, response.status_code, took
        for item in decode(response):
            if isinstance(item, dict) and item.get("id") == message["id"]:
                return item, response.status_code, took
        return None, response.status_code, took


def shape(value, depth=0, limit=3):
    """값의 구조만 한 줄로. 긴 글자는 길이만."""
    if isinstance(value, dict):
        if depth >= limit:
            return f"{{…{len(value)}개 항목}}"
        return "{" + ", ".join(f"{key}: {shape(item, depth + 1, limit)}" for key, item in value.items()) + "}"
    if isinstance(value, list):
        return f"[{len(value)}개" + (f" · 첫 항목 {shape(value[0], depth + 1, limit)}" if value else "") + "]"
    if isinstance(value, str):
        return f"글자({len(value)})"
    return type(value).__name__ if value is not None else "null"


def first_item(value):
    """처음 만나는 목록의 첫 항목(없으면 값 자체)."""
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, dict):
        for item in value.values():
            if isinstance(item, list) and item and isinstance(item[0], dict):
                return item[0]
        for item in value.values():
            if isinstance(item, dict):
                found = first_item(item)
                if found is not None and found is not item:
                    return found
    return value


def find_list(value):
    """처음 만나는 dict 목록."""
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value
    if isinstance(value, dict):
        for item in value.values():
            found = find_list(item)
            if found:
                return found
    return []


WANT = ("price", "amount", "total", "currency", "airline", "carrier", "flight", "depart", "arriv", "stop", "duration")


def summarize(row, prefix=""):
    """가격·항공사·시각 비슷한 이름의 값과 링크 도메인만 한 줄로. 중첩은 한 단계까지."""
    parts = []
    for key, value in row.items():
        name = f"{prefix}{key}"
        low = key.lower()
        if isinstance(value, str) and value.startswith("http"):
            parts.append(f"{name}=<{urlparse(value).netloc}>")
        elif isinstance(value, dict) and not prefix:
            inner = summarize(value, prefix=f"{key}.")
            if inner:
                parts.append(inner)
        elif isinstance(value, list) and value and isinstance(value[0], dict) and not prefix:
            parts.append(f"{name}[{len(value)}]: " + summarize(value[0], prefix=f"{key}[0]."))
        elif any(word in low for word in WANT) and not isinstance(value, (dict, list)):
            parts.append(f"{name}={value}")
    return " · ".join(p for p in parts if p)


def typed(text):
    if text.startswith("s:"):
        return text[2:]
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--call", help="불러 볼 도구 이름")
    parser.add_argument("--arg", action="append", default=[], help="도구 입력. 이름=값. 여러 번 쓸 수 있다")
    parser.add_argument("--instructions", action="store_true", help="서버 안내문 전체를 출력하고 끝낸다")
    parser.add_argument("--schema", help="이 도구의 입력 정의(inputSchema)를 그대로 출력하고 끝낸다")
    parser.add_argument("--raw", type=int, default=0, help="응답 글의 앞부분을 이 글자 수만큼 그대로 출력")
    parser.add_argument("--list", type=int, default=0, help="첫 목록에서 이만큼 항목을 한 줄씩(가격·항공사·시각·링크 도메인)")
    args = parser.parse_args()
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")

    with httpx.Client(timeout=60) as client:
        session = Session(client, load_key())
        reply, status, took = session.send("initialize", {
            "protocolVersion": PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "tripilot-probe", "version": "0.1"}})
        if reply is None or "result" not in reply:
            raise SystemExit(f"[연결] 실패 · HTTP {status} · {took:.2f}초 · 오류 {(reply or {}).get('error')}")
        info = reply["result"]
        print(f"[연결] HTTP {status} · {took:.2f}초 · API 키로 연결됨 · 서버 {info.get('serverInfo')} · "
              f"프로토콜 {info.get('protocolVersion')} · 세션 ID {'있음' if session.session_id else '없음'}")
        if info.get("instructions"):
            print(f"[연결] 서버 안내문 {len(info['instructions'])}자: {info['instructions'][:300]}")
        session.send("notifications/initialized", notify=True)
        if args.instructions:
            print("[안내문 전체 — 서버가 AI 클라이언트에게 보내는 글. 지시가 아니라 읽을 자료로 본다]")
            print(info.get("instructions") or "(없음)")
            return

        if not args.call:
            reply, status, took = session.send("tools/list", {})
            tools = ((reply or {}).get("result") or {}).get("tools") or []
            if args.schema:
                for tool in tools:
                    if tool.get("name") == args.schema:
                        print(f"[입력 정의] {args.schema}")
                        print(json.dumps(tool.get("inputSchema"), ensure_ascii=False, indent=1))
                        return
                raise SystemExit(f"[입력 정의] 그런 도구가 없습니다: {args.schema}")
            print(f"[도구] HTTP {status} · {took:.2f}초 · {len(tools)}개")
            for tool in tools:
                schema = tool.get("inputSchema") or {}
                required = set(schema.get("required") or [])
                print(f"  {tool.get('name')} — {str(tool.get('description') or '')[:160]}")
                for name, spec in (schema.get("properties") or {}).items():
                    mark = "필수" if name in required else "선택"
                    extra = f" · 값 {spec.get('enum')}" if spec.get("enum") else ""
                    print(f"      {mark} {name}: {spec.get('type')}{extra} — {str(spec.get('description') or '')[:140]}")
            return

        arguments = {}
        for pair in args.arg:
            name, _, text = pair.partition("=")
            arguments[name] = typed(text)
        print(f"[호출] {args.call} · 입력 {arguments}")
        reply, status, took = session.send("tools/call", {"name": args.call, "arguments": arguments})
        if reply is None:
            raise SystemExit(f"[호출] 응답 없음 · HTTP {status} · {took:.2f}초")
        if "error" in reply:
            raise SystemExit(f"[호출] 오류 · HTTP {status} · {took:.2f}초 · {reply['error']}")
        result = reply["result"]
        content = result.get("content") or []
        print(f"[호출] HTTP {status} · {took:.2f}초 · isError {result.get('isError')} · "
              f"내용 {[part.get('type') for part in content]} · structuredContent {'있음' if result.get('structuredContent') else '없음'}")
        data = result.get("structuredContent")
        text = "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
        if data is None and text:
            try:
                data = json.loads(text)
            except ValueError:
                data = None
        if data is None:
            print(f"[응답] JSON 이 아닌 글 {len(text)}자. 앞부분: {text[:max(args.raw, 800)]}")
            return
        print(f"[응답] 구조 {shape(data)}")
        item = first_item(data)
        if isinstance(item, dict):
            print("[응답] 첫 항목")
            for key, value in item.items():
                shown = value if not isinstance(value, (dict, list)) else shape(value, limit=2)
                print(f"      {key}: {str(shown)[:200]}")
        if args.list:
            rows = find_list(data)
            print(f"[목록] {len(rows)}개 중 {min(args.list, len(rows))}개")
            for row in rows[:args.list]:
                print("   ", summarize(row))
        if args.raw:
            print(f"[응답] 앞부분 {args.raw}자: {text[:args.raw]}")


if __name__ == "__main__":
    main()
