from __future__ import annotations

import select
import shlex
import socket
import socketserver
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Callable

import paramiko


ProgressCallback = Callable[[str], None]


class AutoDLConnectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SSHLogin:
    hostname: str
    port: int
    username: str


def parse_ssh_login_command(command: str) -> SSHLogin:
    """Parse the login command copied from an AutoDL instance page."""

    try:
        parts = shlex.split(command.strip(), posix=True)
    except ValueError as exc:
        raise AutoDLConnectionError("The SSH login command is invalid.") from exc
    if not parts or parts[0].lower() not in {"ssh", "ssh.exe"}:
        raise AutoDLConnectionError(
            "Paste the complete AutoDL command, for example: "
            "ssh -p 12345 root@connect.example.com"
        )

    port = 22
    username = ""
    destination = ""
    index = 1
    while index < len(parts):
        part = parts[index]
        if part == "-p":
            index += 1
            if index >= len(parts):
                raise AutoDLConnectionError("The SSH port is missing.")
            try:
                port = int(parts[index])
            except ValueError as exc:
                raise AutoDLConnectionError("The SSH port is invalid.") from exc
        elif part.startswith("-p") and len(part) > 2:
            try:
                port = int(part[2:])
            except ValueError as exc:
                raise AutoDLConnectionError("The SSH port is invalid.") from exc
        elif part == "-l":
            index += 1
            if index >= len(parts):
                raise AutoDLConnectionError("The SSH user is missing.")
            username = parts[index]
        elif part in {"-i", "-o", "-F", "-J"}:
            index += 1
            if index >= len(parts):
                raise AutoDLConnectionError(
                    f"The value for SSH option {part} is missing."
                )
        elif part.startswith("-"):
            raise AutoDLConnectionError(
                f"Unsupported SSH option in AutoDL command: {part}"
            )
        elif destination:
            raise AutoDLConnectionError(
                "The AutoDL login command must not contain a remote command."
            )
        else:
            destination = part
        index += 1

    if not destination:
        raise AutoDLConnectionError("The SSH host is missing.")
    if "@" in destination:
        destination_user, hostname = destination.rsplit("@", 1)
        username = destination_user or username
    else:
        hostname = destination
    if not username:
        username = "root"
    if not hostname or not 1 <= port <= 65_535:
        raise AutoDLConnectionError("The SSH host or port is invalid.")
    return SSHLogin(hostname=hostname, port=port, username=username)


class _ForwardingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _handler_for(
    transport: paramiko.Transport,
    remote_address: tuple[str, int],
):
    class ForwardHandler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            try:
                channel = transport.open_channel(
                    "direct-tcpip",
                    remote_address,
                    self.request.getpeername(),
                )
            except Exception:
                return
            if channel is None:
                return
            try:
                while True:
                    readable, _, _ = select.select(
                        [self.request, channel],
                        [],
                        [],
                        1.0,
                    )
                    if self.request in readable:
                        data = self.request.recv(65_536)
                        if not data:
                            break
                        channel.sendall(data)
                    if channel in readable:
                        data = channel.recv(65_536)
                        if not data:
                            break
                        self.request.sendall(data)
            finally:
                channel.close()

    return ForwardHandler


class AutoDLTTSConnection:
    """Own one AutoDL SSH session, remote command, and local port forward."""

    def __init__(self) -> None:
        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None
        self._server: _ForwardingServer | None = None
        self._server_thread: threading.Thread | None = None
        self._output_thread: threading.Thread | None = None
        self._output: deque[str] = deque(maxlen=80)

    def is_active(self) -> bool:
        transport = (
            self._client.get_transport()
            if self._client is not None
            else None
        )
        return bool(transport is not None and transport.is_active())

    def start(
        self,
        login_command: str,
        password: str,
        remote_command: str,
        *,
        local_address: tuple[str, int] = ("127.0.0.1", 9880),
        remote_address: tuple[str, int] = ("127.0.0.1", 9880),
        progress: ProgressCallback | None = None,
    ) -> None:
        if self.is_active():
            return
        self.stop()
        login = parse_ssh_login_command(login_command)
        if not password:
            raise AutoDLConnectionError("Enter the AutoDL SSH password.")
        if not remote_command.strip():
            raise AutoDLConnectionError(
                "Enter the command used to start TTS on AutoDL."
            )

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if progress is not None:
                progress("connecting_ssh")
            client.connect(
                hostname=login.hostname,
                port=login.port,
                username=login.username,
                password=password,
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
                allow_agent=False,
                look_for_keys=False,
            )
            transport = client.get_transport()
            if transport is None or not transport.is_active():
                raise AutoDLConnectionError("The AutoDL SSH session is inactive.")
            transport.set_keepalive(20)

            if progress is not None:
                progress("starting_remote")
            channel = transport.open_session(timeout=15)
            channel.get_pty(term="xterm", width=120, height=40)
            channel.set_combine_stderr(True)
            channel.exec_command(remote_command)

            if progress is not None:
                progress("starting_tunnel")
            server = _ForwardingServer(
                local_address,
                _handler_for(transport, remote_address),
            )
            server_thread = threading.Thread(
                target=server.serve_forever,
                name="aipet-autodl-forward",
                daemon=True,
            )
            output_thread = threading.Thread(
                target=self._drain_output,
                args=(channel,),
                name="aipet-autodl-output",
                daemon=True,
            )
            self._client = client
            self._channel = channel
            self._server = server
            self._server_thread = server_thread
            self._output_thread = output_thread
            server_thread.start()
            output_thread.start()
        except Exception as exc:
            client.close()
            if isinstance(exc, AutoDLConnectionError):
                raise
            if isinstance(exc, OSError) and exc.errno in {10048, 98}:
                raise AutoDLConnectionError(
                    f"Local port {local_address[1]} is already in use."
                ) from exc
            raise AutoDLConnectionError(
                f"Could not start the AutoDL SSH connection: {exc}"
            ) from exc

    def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        channel = self._channel
        self._channel = None
        if channel is not None:
            try:
                if not channel.closed:
                    channel.send(b"\x03")
            except (OSError, socket.error):
                pass
            channel.close()
        client = self._client
        self._client = None
        if client is not None:
            client.close()
        self._server_thread = None
        self._output_thread = None

    def output_tail(self) -> str:
        return "\n".join(self._output)

    def read_reference_metadata(
        self,
        reference_root: str,
        emotion: str,
    ) -> tuple[str, str]:
        client = self._client
        if client is None or not self.is_active():
            raise AutoDLConnectionError(
                "The AutoDL SSH session is not active."
            )
        directory = PurePosixPath(reference_root) / emotion
        sftp = client.open_sftp()
        try:
            names = sorted(sftp.listdir(str(directory)))
            audio_name = next(
                (
                    name
                    for name in names
                    if PurePosixPath(name).suffix.lower()
                    in {".wav", ".mp3", ".flac"}
                ),
                "",
            )
            if not audio_name or "asr.txt" not in names:
                raise AutoDLConnectionError(
                    f"Remote reference voice is incomplete: {directory}"
                )
            transcript_file = sftp.open(
                str(directory / "asr.txt"),
                "rb",
            )
            try:
                transcript = transcript_file.read().decode("utf-8").strip()
            finally:
                transcript_file.close()
            if not transcript:
                raise AutoDLConnectionError(
                    f"Remote reference transcript is empty: {directory}"
                )
            return str(directory / audio_name), transcript
        except AutoDLConnectionError:
            raise
        except (OSError, UnicodeError) as exc:
            raise AutoDLConnectionError(
                f"Could not read the AutoDL reference voice: {exc}"
            ) from exc
        finally:
            sftp.close()

    def _drain_output(self, channel: paramiko.Channel) -> None:
        pending = b""
        while not channel.closed:
            try:
                data = channel.recv(4096)
            except (OSError, socket.error):
                return
            if not data:
                break
            pending += data
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                self._output.append(
                    line.decode("utf-8", errors="replace").rstrip()
                )
        if pending:
            self._output.append(
                pending.decode("utf-8", errors="replace").rstrip()
            )
