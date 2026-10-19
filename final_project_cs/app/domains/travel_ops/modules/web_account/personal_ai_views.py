"""인증 전용 HTML. 공용 고객 웹 스타일·스크립트를 수정하지 않는다."""
import html
import secrets

from fastapi.responses import HTMLResponse

STYLE = """*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#182235;font:16px/1.6 system-ui,sans-serif}
main{width:min(100% - 32px,560px);margin:48px auto;background:#fff;border:1px solid #d6dce5;border-radius:12px;padding:32px}
h1{font-size:24px;line-height:1.25;font-weight:600;margin:4px 0 24px}strong{font-weight:600}p{margin:16px 0;max-width:70ch;overflow-wrap:anywhere}a{display:inline-block;min-height:44px;padding:8px 0;color:#174cb5;text-underline-offset:3px}
button{min-height:44px;padding:10px 18px;border:1px solid #174cb5;border-radius:6px;background:#174cb5;color:#fff;font:inherit;cursor:pointer}
button[value=deny]{background:#fff;color:#174cb5}form{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0 8px}
:focus-visible{outline:3px solid #103b90;outline-offset:3px}ul{padding:0;list-style:none}li{padding:20px 0;border-top:1px solid #d6dce5}
.eyebrow{font-size:14px;font-weight:600;color:#526078;margin:0}.muted{color:#526078;font-size:14px}
label{display:block;width:100%}input,select{display:block;width:100%;min-height:44px;padding:8px;border:1px solid #8792a4;border-radius:4px;background:#fff;color:#182235;font:inherit}
.list-frame{border:1px solid #d6dce5;border-radius:6px;padding:0 20px}.list-frame ul{margin:0}.list-frame li:first-child{border-top:0}
.action{display:inline-flex;align-items:center;min-height:44px;padding:8px 0;margin-right:12px}.danger{background:#a52025;border-color:#a52025}
@media(max-width:767px){main{margin:16px auto;padding:24px}button{flex:1}form{gap:8px}}
"""


def document(title, body):
    nonce = secrets.token_urlsafe(16)
    return HTMLResponse(f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>"
        f"<style nonce='{nonce}'>{STYLE}</style></head><body><main id='main'><p class='eyebrow'>guguroute · 개인 AI 연결</p>"
        f"{body}</main></body></html>", headers={"Cache-Control": "no-store", "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": f"default-src 'none'; style-src 'nonce-{nonce}'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
