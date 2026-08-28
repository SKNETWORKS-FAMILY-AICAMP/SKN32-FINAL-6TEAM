# -*- coding: utf-8 -*-
"""검증용 가짜 대상. 대상의 Composer 계약만 흉내 낸다.

/apply 는 대상과 똑같이 reason 을 필수로 요구하고, 없으면 422 를 낸다.
고친 코드가 실제로 사유를 보내는지 브라우저로 확인하려고 만들었다.
"""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

ISSUER = "issuer-secret"
STATE = {"revision": "rev-1", "config": {
    "modules": {"vector_rag": {"enabled": True}, "a2a_executor": {"enabled": False}},
    "ports": {"team_executor": "local"},
    "teams": [{"team_id": "voc_store_manager", "active": True,
               "implementation_ref": "app.modules.customer_ops:VocStoreManagerTeam"}],
}}
SEEN = []


class H(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode()) if n else None

    def do_GET(self):
        if self.path == "/introspection":
            return self._json(200, {"contract_version": "1.0",
                                    "config_revision": STATE["revision"],
                                    "modules": {"vector_rag": True, "a2a_executor": False},
                                    "ports": {"team_executor": "local"},
                                    "teams": [{"team_id": "voc_store_manager", "active": True}],
                                    "registered_ids": {"modules": ["vector_rag", "a2a_executor"],
                                                       "teams": ["voc_store_manager"], "ports": []},
                                    "team_manifests": [], "port_implementations": {},
                                    "guardrails": {}, "llm": {}})
        if self.path == "/composer/current":
            return self._json(200, {"revision": STATE["revision"], "config": STATE["config"]})
        self._json(404, {})

    def do_POST(self):
        body = self._body()
        if self.path == "/auth/token":
            if self.headers.get("Authorization") != f"Bearer {ISSUER}":
                return self._json(401, {"error": {"message": "issuer rejected"}})
            return self._json(200, {"access_token": "access", "token_type": "bearer", "expires_in": 900})
        if self.path == "/composer/validate":
            SEEN.append((self.path, body))
            return self._json(200, {"valid": True, "revision": STATE["revision"]})
        if self.path == "/composer/apply":
            SEEN.append((self.path, body))
            # ★대상과 같은 규칙: reason 이 없거나 비면 422
            if not (body or {}).get("reason", "").strip():
                return self._json(422, {"error": {"code": "invalid_payload",
                                                  "message": "reason: Field required (min_length=1)"}})
            if body.get("base_revision") != STATE["revision"]:
                return self._json(409, {"error": {"message": "stale",
                                                  "current_revision": STATE["revision"]}})
            STATE["revision"] = "rev-2"
            STATE["config"] = body["config"]
            return self._json(200, {"revision": STATE["revision"], "applied": True})
        self._json(404, {})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8076), H).serve_forever()
