"""마이리얼트립 MCP 서버가 인증 없이 실제로 답하는지, 도구와 응답에 무엇이 있는지 본다.

- 주소: https://mcp-servers.myrealtrip.com/mcp (문서 docs.myrealtrip.com 의 MCP 개요, 2026-10-07 확인)
- 키가 필요 없다. 검색만 하고 예약·결제·로그인은 하지 않는다.
- 응답 원문은 저장하지 않는다. 구조(항목 이름·개수)와 첫 항목만 출력한다.

실행 위치: final_project_cs
  python -m scripts.probe_myrealtrip_mcp                      # 도구 목록과 입력 항목
  python -m scripts.probe_myrealtrip_mcp --call getCurrentTime
  python -m scripts.probe_myrealtrip_mcp --url https://mcp.kiwi.com      # [2026-10-09] 다른 키 없는 MCP(Kiwi.com)
  python -m scripts.probe_myrealtrip_mcp --schema searchInternationalFlights   # 그 도구의 입력 정의 원문
  python -m scripts.probe_myrealtrip_mcp --call 도구이름 --arg 이름=값 --arg 이름=값
값은 숫자·true/false 면 그 형으로, 나머지는 글자로 보낸다. 숫자처럼 생긴 값을 글자로 보내려면 값 앞에 s: 를 붙인다(예: --arg code=s:123).
"""
from argparse import ArgumentParser
from datetime import datetime
import json
import platform
import time
from zoneinfo import ZoneInfo

import httpx

URL = "https://mcp-servers.myrealtrip.com/mcp"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
PROTOCOL = "2025-03-26"


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
    def __init__(self, client, url=URL):
        self.client, self.session_id, self.next_id, self.url = client, None, 0, url
        self.limit_headers = {}

    def send(self, method, params=None, *, notify=False):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            self.next_id += 1
            message["id"] = self.next_id
        headers = dict(HEADERS)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        started = time.perf_counter()
        response = self.client.post(self.url, json=message, headers=headers)
        took = time.perf_counter() - started
        # `[2026-10-10]` 호출 한도 확인 — 파트너 REST 문서는 `X-RateLimit-*` 헤더 · 429 를 말한다. MCP 도 주는지 본다
        self.limit_headers = {name: value for name, value in response.headers.items()
                              if any(word in name.lower() for word in ("ratelimit", "rate-limit", "retry-after", "quota", "x-limit"))}
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
    parser.add_argument("--url", default=URL, help="MCP 주소(기본 마이리얼트립). 키 없이 여는 다른 서버를 볼 때. 예: https://mcp.kiwi.com")
    parser.add_argument("--call", help="불러 볼 도구 이름")
    parser.add_argument("--arg", action="append", default=[], help="도구 입력. 이름=값. 여러 번 쓸 수 있다")
    parser.add_argument("--instructions", action="store_true", help="서버 안내문 전체를 출력하고 끝낸다")
    parser.add_argument("--schema", help="이 도구의 입력 정의(inputSchema)를 그대로 출력하고 끝낸다")
    parser.add_argument("--raw", type=int, default=0, help="응답 글의 앞부분을 이 글자 수만큼 그대로 출력")
    args = parser.parse_args()
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")

    with httpx.Client(timeout=60) as client:
        session = Session(client, args.url)
        print(f"[주소] {args.url}")
        reply, status, took = session.send("initialize", {
            "protocolVersion": PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "tripilot-probe", "version": "0.1"}})
        if reply is None or "result" not in reply:
            raise SystemExit(f"[연결] 실패 · HTTP {status} · {took:.2f}초 · 오류 {(reply or {}).get('error')}")
        info = reply["result"]
        print(f"[한도 헤더] {session.limit_headers or '없음'}")
        print(f"[연결] HTTP {status} · {took:.2f}초 · 인증 없이 연결됨 · 서버 {info.get('serverInfo')} · "
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
            raise SystemExit(f"[호출] 응답 없음 · HTTP {status} · {took:.2f}초 · 한도 헤더 {session.limit_headers or '없음'}")
        if "error" in reply:
            raise SystemExit(f"[호출] 오류 · HTTP {status} · {took:.2f}초 · {reply['error']}")
        print(f"[한도 헤더] {session.limit_headers or '없음'}")
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
        if args.raw:
            print(f"[응답] 앞부분 {args.raw}자: {text[:args.raw]}")


if __name__ == "__main__":
    main()
