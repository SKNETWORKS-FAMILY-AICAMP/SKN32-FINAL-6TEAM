# -*- coding: utf-8 -*-
"""서버에 둘 환경 파일 **둘**(`.env` · `.env.apikeys`)을 이 PC 의 값으로 만든다 — 비밀은 화면에도 로그에도 찍지 않는다. `[2026-10-03]`

    python deploy/make_server_env.py --host <공개 도메인> --proxy-network <프록시 네트워크 이름> --proxy-cidr <프록시 대역> --out <파일>

★`[2026-10-04 사용자 지시]` **이 PC 와 같은 구조로 둘로 나눈다** — `.env`(앱 설정 · 서버에서 새로 만든 비밀) · `.env.apikeys`(바깥 데이터 소스 키만, 이 PC 의 `.env.apikeys` 에서 옮김).
  이 PC 의 설정 코드가 두 파일을 읽는 이유(키만 따로 갈아 끼우게)가 서버에도 그대로 맞는다. `--out` 이 `.env`, `--out-apikeys`(기본: `--out` 옆의 `.env.apikeys`)가 키 파일이다.
★테넌트 이름은 `live` 다(`ACOP_TENANT_ID`) — 서버 DB 의 데이터가 이 이름으로 쌓인다. 앞 판은 이 PC 의 개발 이름 `demo` 를 그대로 썼다.

★만드는 규칙:
  - **새로 만든다**(서버 전용): DB 비밀번호 · `ACOP_SECRET_KEY` · Composer 비밀 둘. 개발 PC 의 것을 옮기지 않는다 — 개발 DB 의 암호화된 값(디스코드 웹훅 등)은 이 서버로 안 가므로 옮길 이유도 없다.
  - **옮긴다**: `.env.apikeys` 의 **공공 데이터 · 지도 키**(관광공사 · 기상청 · 에어코리아 …)와 일일 호출 상한(`ACOP_RATE_*`). 상한이 이 서버에서도 지켜진다.
  - **옮기지 않는다**: 디스코드 웹훅(옮길 때 새로 발급하는 것이 원칙 — `wiki/operations/move-to-server.md` §3) · 고정 IP 경유 설정(`ACOP_OUTBOUND_PROXY_*`) 과 그 IP 에 묶인 키(UTIC) ·
    OpenAI 키(기본 모델은 Ollama — 요금이 안 나간다) · 개발용 운영자 계정.
  - 모델 서버 주소는 인자로 받는다(`--ollama-url`). 기본 모델 이름은 개발과 같다.
★출력 파일은 **비밀이다** — 서버로 옮긴 뒤 이 PC 의 사본을 지운다. 이 스크립트는 값을 한 글자도 표준 출력에 내지 않는다(이름 · 개수만).
"""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path

CS_ROOT = Path(__file__).resolve().parents[1]

#: `.env.apikeys` 에서 **옮기지 않는** 이름 — 이유는 위 docstring.
SKIP = {
    "ACOP_DISCORD_WEBHOOK_URL", "ACOP_OUTBOUND_PROXY_URL", "ACOP_OUTBOUND_PROXY_SOURCES",
    "ACOP_UTIC_API_KEY_1", "ACOP_UTIC_API_KEY_2", "ACOP_RATE_UTIC_PER_DAY",
    "ACOP_OPENAI_API_KEY", "ACOP_OPENAI_API_KEY_SERVER",
    # 소셜 로그인 클라이언트 — 이 PC 의 값을 자동으로 옮기지 않는다(비밀이 실수로 옮겨지지 않게). 서버 값은 서버 `.env` 에 직접 넣는다(wiki/operations/google-login-setup.md)
    "ACOP_GOOGLE_CLIENT_ID", "ACOP_GOOGLE_CLIENT_SECRET", "ACOP_WEB_ORIGIN",
}


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="공개 도메인(예: 서비스 주소의 호스트 이름)")
    parser.add_argument("--proxy-network", required=True)
    parser.add_argument("--proxy-cidr", required=True, help="역방향 프록시가 속한 네트워크 대역 — 이 대역에서 온 요청만 X-Forwarded-For 를 믿는다")
    parser.add_argument("--ollama-url", default="", help="모델 서버 주소(Ollama). 비우면 모델 기능이 꺼진다")
    parser.add_argument("--out", required=True, help="`.env` 를 쓸 파일")
    parser.add_argument("--out-apikeys", default="", help="`.env.apikeys` 를 쓸 파일(기본: --out 옆의 .env.apikeys)")
    args = parser.parse_args()

    keys = read_env(CS_ROOT / ".env.apikeys")
    moved = {k: v for k, v in keys.items() if k not in SKIP and v}
    public = f"https://{args.host}"
    lines = [
        "# 서버 전용 — git 에 올리지 않는다. 비밀이다.",
        f"TRIPILOT_PUBLIC_URL={public}",
        f"TRIPILOT_PROXY_NETWORK={args.proxy_network}",
        f"TRIPILOT_DB_PASSWORD={secrets.token_urlsafe(32)}",
        "",
        "ACOP_ENV=public",
        "ACOP_TENANT_ID=live",
        f"ACOP_SECRET_KEY={secrets.token_hex(32)}",
        f"ACOP_COMPOSER_JWT_SECRET={secrets.token_hex(32)}",
        f"ACOP_COMPOSER_ISSUER_SECRET={secrets.token_hex(32)}",
        f"ACOP_PUBLIC_BASE_URL={public}",
        f"ACOP_WEB_ALLOWED_ORIGINS={public}",
        f"ACOP_TRUSTED_PROXIES={args.proxy_cidr}",
        "",
        # ★설정 검사가 이 셋을 **필수**로 요구한다(모델 서버만 써도) — 키는 비워 둔다(요금이 안 나간다). 모델 이름은 Ollama 경로에서 안 쓰인다
        "ACOP_OPENAI_API_KEY=",
        "ACOP_LLM_MODEL=gpt-4o-mini",
        "ACOP_EMBEDDING_MODEL=text-embedding-3-small",
        "ACOP_LLM_PROVIDER=openai",
        f"ACOP_OLLAMA_BASE_URL={args.ollama_url}",
        # ★`[2026-10-14 사용자 지시]` 요청 해석(할 일 고르기)도 **우리 데이터로 학습한 E4B** 하나로 — 일정 짚기와 같은 모델이라 12GB GPU 에서 교체가 없다.
        #   434 문장 재생(채점용 126): 할 일 85% · 대상 78% — 학습 없는 12B 74%·72%, 유료 대체 79%·67%보다 낫고 더 빠르다
        #   (datasets/core/chat_probe/2026-10-13_x600_web_chat/replay/RESULTS.md). 문맥 길이는 아래 8,192 와 함께여야 한다(기본 4,096 이면 입력이 잘린다)
        #   (같은 날 코드 기본값도 이 모델로 바꿨다 — 운영 설정과 어긋나 있던 것을 맞췄다. 줄은 명시적으로 남긴다)
        "ACOP_OLLAMA_MODEL=tripilot-pointer:e4b-ft",
        "ACOP_OLLAMA_POINTER_MODEL=tripilot-pointer:e4b-ft",
        "ACOP_OLLAMA_NUM_CTX=8192",
        # ★`[2026-10-14 x600 실측]` 학습 E4B 해석 한 건 5.1~7.3초(지시문 읽기 약 2초는 문장마다 다시 든다) — 6초면 8건 중 6건이 유료 대체로 넘어갔다.
        #   9초면 8/8 로컬(같은 날 코드 기본값도 6 → 9초로 올렸다 — 줄은 명시적으로 남긴다). 넘어가도 유료 대체(2~3초)까지 고객 응답 15초 안이다
        "ACOP_LLM_FAILOVER_PRIMARY_TIMEOUT_SECONDS=9",
        # 식은 모델 로딩이 30~64초 걸렸다(2026-10-03 실측) — 기본 60초면 첫 호출이 로딩 중에 끊기고, 끊으면 모델 서버가 로딩을 버린다
        "ACOP_OLLAMA_TIMEOUT_SECONDS=150",
        "ACOP_EMBEDDING_PROVIDER=ollama",
        "ACOP_OLLAMA_EMBEDDING_MODEL=bge-m3:latest",
    ]
    out = Path(args.out)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")      # BOM 없이 · LF
    apikeys = Path(args.out_apikeys) if args.out_apikeys else out.with_name(".env.apikeys")
    apikeys.write_text("\n".join(["# 서버 전용 — git 에 올리지 않는다. 비밀이다. 바깥 데이터 소스 키만(공공 데이터 · 지도 — 이 PC 의 .env.apikeys 에서 옮김).",
                                   *(f"{k}={v}" for k, v in moved.items())]) + "\n", encoding="utf-8", newline="\n")
    print(f"쓴 파일: {out.name} · {apikeys.name} · 새로 만든 비밀 5 · 옮긴 키/설정 {len(moved)}개 · 안 옮긴 이름 {len(SKIP & set(keys))}개")


if __name__ == "__main__":
    main()
