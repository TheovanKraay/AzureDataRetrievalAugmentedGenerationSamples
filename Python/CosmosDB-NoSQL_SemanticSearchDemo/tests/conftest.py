import os
import ipaddress
import socket

import pytest


@pytest.fixture(autouse=True)
def offline_guard(request, monkeypatch):
    if request.node.get_closest_marker("live"):
        if os.getenv("RUN_LIVE_TESTS") != "1":
            pytest.skip("Set RUN_LIVE_TESTS=1 to enable Azure tests.")
        for key in ("COSMOS_URI", "COSMOS_DB_DATABASE", "AZURE_AI_INFERENCE_ENDPOINT"):
            if not os.getenv(key):
                pytest.fail(f"Live tests enabled but {key} is missing.")
        return

    def is_loopback(host):
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return host in ("localhost", b"localhost")

    def guard_connection(original):
        def guarded(connection, address):
            if not isinstance(address, tuple) or not is_loopback(address[0]):
                raise AssertionError("Offline test attempted external network access")
            return original(connection, address)
        return guarded

    # Windows asyncio creates a loopback socketpair for its wake-up pipe.
    # Permit local runtime IPC, not Azure/service connections.
    monkeypatch.setattr(socket.socket, "connect", guard_connection(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard_connection(socket.socket.connect_ex))
    original_sendto = socket.socket.sendto
    original_getaddrinfo = socket.getaddrinfo

    def guarded_sendto(connection, *args):
        address = args[-1]
        if not isinstance(address, tuple) or not is_loopback(address[0]):
            raise AssertionError("Offline test attempted external network access")
        return original_sendto(connection, *args)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host is not None and not is_loopback(host):
            raise AssertionError("Offline test attempted external DNS/network access")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    # No local developer configuration may leak into offline tests.
    monkeypatch.setenv("DEMO_LOAD_DOTENV", "false")
    for key in ("COSMOS_URI", "COSMOS_DB_DATABASE", "AZURE_AI_INFERENCE_ENDPOINT",
                "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"):
        monkeypatch.delenv(key, raising=False)
