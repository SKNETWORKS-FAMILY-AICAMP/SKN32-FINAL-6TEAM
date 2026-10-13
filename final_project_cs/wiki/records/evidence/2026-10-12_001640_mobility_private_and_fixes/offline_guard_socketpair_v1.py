"""오프라인 검증: 현재 스레드의 표준 socketpair 내부 IPC만 허용한다."""
import ipaddress
import socket
import threading

import pytest


class OfflineOnly:
    @pytest.fixture(autouse=True)
    def prevent_external_connections(self, monkeypatch):
        original_connect = socket.socket.connect
        original_pair = socket.socketpair
        context = threading.local()

        def reject(*args, **kwargs):
            raise AssertionError("This validation run forbids network connections")

        def guarded_connect(sock, address):
            if getattr(context, "socketpair_depth", 0) > 0:
                if isinstance(address, tuple) and address and isinstance(address[0], str):
                    try:
                        local = ipaddress.ip_address(address[0]).is_loopback
                    except ValueError:
                        local = False
                    if local:
                        return original_connect(sock, address)
            return reject(sock, address)

        def internal_socketpair(*args, **kwargs):
            depth = getattr(context, "socketpair_depth", 0)
            context.socketpair_depth = depth + 1
            try:
                # Python의 표준 구현만 이 범위에서 실행한다. 임의 로컬 서비스
                # 접속이나 다른 스레드의 연결에는 예외를 주지 않는다.
                return original_pair(*args, **kwargs)
            finally:
                context.socketpair_depth = depth

        monkeypatch.setattr(socket.socket, "connect", guarded_connect)
        monkeypatch.setattr(socket.socket, "connect_ex", reject)
        monkeypatch.setattr(socket, "create_connection", reject)
        monkeypatch.setattr(socket, "socketpair", internal_socketpair)
