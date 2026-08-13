"""DockerSession.create() exec_start 返回形态兼容单元测试（无需真实 Docker）。

根因：docker SDK 7.x 起，exec_start(socket=True) 不再返回旧版 SocketAdapter
（带 _sock 属性），在 Docker Desktop (Windows) 下返回
docker.transport.npipesocket.NpipeSocket —— 实现了完整 socket API 但无 _sock，
旧代码 hasattr(socket_data, "_sock") 恒为 False → 抛 RuntimeError。
"""

import asyncio
import time

import pytest

from app.sandbox.core.terminal import DockerSession


class _FakeSocket:
    """模拟 docker SDK 7.x 返回的 socket 兼容对象（NpipeSocket / raw socket）。

    有 recv/sendall/setblocking 等完整 socket API，无 _sock 属性。
    """

    def __init__(self, data: bytes = b"$ "):
        self._data = data
        self.setblocking_called = False
        self.closed = False

    def setblocking(self, flag: bool) -> None:
        self.setblocking_called = True

    def recv(self, n: int) -> bytes:
        if not self._data:
            raise BlockingIOError("模拟非阻塞无数据")
        chunk, self._data = self._data[:n], self._data[n:]
        return chunk

    def sendall(self, data: bytes) -> None:
        pass

    def shutdown(self, how: int) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _FakeAdapter:
    """模拟旧版 docker SDK 的 SocketAdapter：自身无 recv，底层 socket 在 _sock 里。"""

    def __init__(self):
        self._sock = _FakeSocket()

    def read(self, n: int) -> bytes:  # io.RawIOBase 风格
        return self._sock.recv(n)


class _FakeUnusable:
    """既无 socket API 也无 _sock 的异常返回对象。"""


class _BlockingSocket:
    """模拟 NpipeSocket：recv 同步阻塞（time.sleep），不抛 EWOULDBLOCK。

    Docker Desktop Windows 下 NpipeSocket.recv 是同步 win32file.ReadFile，
    setblocking(False) 对其无效 —— 阻塞期间 asyncio.wait_for 无法取消
    直接调用它的协程（无暂停点），必须经 asyncio.to_thread 才能超时。
    """

    def __init__(self, block_seconds: float, then_return: bytes = b"$ "):
        self._block = block_seconds
        self._then = then_return

    def setblocking(self, flag: bool) -> None:
        pass

    def recv(self, n: int) -> bytes:
        time.sleep(self._block)  # 模拟同步阻塞
        return self._then

    def sendall(self, data: bytes) -> None:
        pass

    def shutdown(self, how: int) -> None:
        pass

    def close(self) -> None:
        pass


def _make_session(monkeypatch, socket_data):
    session = DockerSession("fake_container")
    monkeypatch.setattr(session.api, "exec_create", lambda *a, **k: {"Id": "exec123"})
    monkeypatch.setattr(session.api, "exec_start", lambda *a, **k: socket_data)
    return session


class TestDockerSessionCreate:
    """DockerSession.create() 对 exec_start 返回形态的兼容。"""

    @pytest.mark.asyncio
    async def test_accepts_direct_socket_object(self, monkeypatch):
        """SDK 7.x：返回无 _sock 的 socket 兼容对象时，直接使用，不得报错。"""
        fake = _FakeSocket()
        session = _make_session(monkeypatch, fake)

        await session.create("/workspace", {})

        assert session.socket is fake
        assert fake.setblocking_called is True
        assert session.exec_id == "exec123"

    @pytest.mark.asyncio
    async def test_still_supports_adapter_wrapper(self, monkeypatch):
        """旧版 SDK：返回带 _sock 的包装对象时，解包底层 socket 使用。"""
        fake = _FakeAdapter()
        session = _make_session(monkeypatch, fake)

        await session.create("/workspace", {})

        assert session.socket is fake._sock
        assert fake._sock.setblocking_called is True

    @pytest.mark.asyncio
    async def test_rejects_unusable_object(self, monkeypatch):
        """两者皆无时仍抛 RuntimeError，保留防御语义。"""
        session = _make_session(monkeypatch, _FakeUnusable())

        with pytest.raises(RuntimeError, match="Failed to get socket connection"):
            await session.create("/workspace", {})

    @pytest.mark.asyncio
    async def test_execute_timeout_interrupts_blocking_recv(self, monkeypatch):
        """同步阻塞的 recv（NpipeSocket）可被超时中断。

        回归：asyncio.wait_for 无法取消直接阻塞在同步 recv 上的协程，
        必须经 asyncio.to_thread 执行 recv，超时才能生效。
        """
        fake = _BlockingSocket(block_seconds=3.0)
        session = _make_session(monkeypatch, fake)
        session.socket = fake  # 模拟 create() 已完成初始化

        t0 = time.monotonic()
        with pytest.raises(TimeoutError):
            await session.execute("sleep 5", timeout=0.3)
        elapsed = time.monotonic() - t0

        assert elapsed < 2.0, f"超时应在约 0.3s 触发，实际 {elapsed:.1f}s（recv 未被中断）"


if __name__ == "__main__":
    asyncio.run(TestDockerSessionCreate().test_accepts_direct_socket_object(None))
