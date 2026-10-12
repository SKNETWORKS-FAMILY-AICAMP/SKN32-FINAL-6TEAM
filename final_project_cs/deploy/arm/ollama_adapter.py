"""기존 llama.cpp 추론 결과를 앱의 Ollama 계약으로 옮긴다. 답을 생성하는 대역이 아니다."""
import json
import hashlib
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def upstream(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


def chat_payload(data):
    if data.get("stream") or any(m.get("images") for m in data.get("messages", [])):
        raise ValueError("이 ARM 연결은 비스트리밍 텍스트만 지원합니다")
    if data.get("model") != os.environ["CHAT_MODEL"]:
        raise ValueError("설정된 상주 모델과 요청 모델이 다릅니다")
    options = data.get("options", {})
    payload = {"messages": data["messages"], "stream": False,
               "temperature": options.get("temperature", 0),
               "max_tokens": options.get("num_predict", 512), "cache_prompt": True}
    if "think" in data:
        if not isinstance(data["think"], bool):
            raise ValueError("think 값은 참 또는 거짓이어야 합니다")
        payload["chat_template_kwargs"] = {"enable_thinking": data["think"]}
    if "seed" in options:
        payload["seed"] = options["seed"]
    schema = data.get("format")
    if isinstance(schema, dict):
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema}}
    elif schema == "json":
        payload["response_format"] = {"type": "json_object"}
    return payload


def check_model(url, expected):
    rows = upstream(url + "/v1/models")["data"]
    if expected not in [row["id"] for row in rows]:
        raise RuntimeError("실행 모델이 설정과 다릅니다")


class ModelOutputError(RuntimeError):
    """고객 입력 오류와 모델의 불완전 응답을 구분한다. 원문은 노출하지 않는다."""
    def __init__(self, code, diagnostics):
        super().__init__(code)
        self.code = code
        self.diagnostics = diagnostics


def chat_response(result, request):
    diagnostics = {}
    try:
        choice = result["choices"][0]
        content = choice["message"]["content"]
        reason = choice.get("finish_reason")
        diagnostics = {"finish_reason": reason,
                       "content_characters": len(content) if isinstance(content, str) else None,
                       "content_sha256": hashlib.sha256(content.encode()).hexdigest() if isinstance(content, str) else None,
                       "usage": result.get("usage", {}), "timings": result.get("timings", {})}
    except (KeyError, IndexError, TypeError):
        raise ModelOutputError("invalid_model_response", diagnostics) from None
    if not isinstance(content, str) or not content.strip():
        raise ModelOutputError("empty_model_output", diagnostics)
    if reason != "stop":
        raise ModelOutputError("incomplete_model_output", diagnostics)
    if isinstance(request.get("format"), dict) or request.get("format") == "json":
        def unique_object(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError("duplicate key")
                obj[key] = value
            return obj
        def reject_constant(value):
            raise ValueError("nonfinite number")
        try:
            json.loads(content, object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (ValueError, RecursionError):
            raise ModelOutputError("invalid_model_json", diagnostics) from None
    return {"message": {"role": "assistant", "content": content}, "done": True,
            "done_reason": reason, "usage": diagnostics["usage"], "timings": diagnostics["timings"]}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            upstream(os.environ["CHAT_URL"] + "/health")
            check_model(os.environ["CHAT_URL"], os.environ["CHAT_ID"])
            if self.path not in ("/health", "/api/ps"):
                self.reply(404, {"error": "unknown route"})
                return
            self.reply(200, {"models": [{"name": os.environ["CHAT_MODEL"], "model": os.environ["CHAT_MODEL"]}]})
        except Exception as exc:
            self.reply(502, {"error": type(exc).__name__})

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                raise ValueError("request size")
            data = json.loads(self.rfile.read(size))
            if self.path == "/api/chat":
                payload = chat_payload(data)
                try:
                    check_model(os.environ["CHAT_URL"], os.environ["CHAT_ID"])
                    result = upstream(os.environ["CHAT_URL"] + "/v1/chat/completions", payload)
                except (ValueError, KeyError, TypeError):
                    raise ModelOutputError("invalid_model_response", {}) from None
                self.reply(200, chat_response(result, data))
            elif self.path == "/api/embed":
                if data.get("model") != os.environ["EMBED_MODEL"]:
                    raise ValueError("embedding model mismatch")
                check_model(os.environ["EMBED_URL"], os.environ["EMBED_ID"])
                result = upstream(os.environ["EMBED_URL"] + "/v1/embeddings", {"input": data["input"]})
                rows = sorted(result["data"], key=lambda row: row["index"])
                self.reply(200, {"embeddings": [row["embedding"] for row in rows]})
            else:
                self.reply(404, {"error": "unknown route"})
        except ModelOutputError as exc:
            self.reply(502, {"error": exc.code, "diagnostics": exc.diagnostics})
        except (ValueError, KeyError, TypeError) as exc:
            self.reply(400, {"error": str(exc)})
        except Exception as exc:
            self.reply(502, {"error": type(exc).__name__})

    def log_message(self, fmt, *args):
        # 질의 본문·인증 키는 기록하지 않는다.
        print(fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("ADAPTER_PORT", "18312"))), Handler).serve_forever()
