from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import Mock, patch

from tool.autodl_tts import (
    AutoDLConnectionError,
    AutoDLTTSConnection,
    SSHLogin,
    parse_ssh_login_command,
)
from tool.credentials import protect_secret, unprotect_secret


class AutoDLTTSTests(unittest.TestCase):
    def test_parses_command_copied_from_autodl(self) -> None:
        self.assertEqual(
            parse_ssh_login_command(
                "ssh -p 12345 root@connect.cqa1.seetacloud.com"
            ),
            SSHLogin(
                hostname="connect.cqa1.seetacloud.com",
                port=12345,
                username="root",
            ),
        )

    def test_rejects_login_command_with_remote_payload(self) -> None:
        with self.assertRaises(AutoDLConnectionError):
            parse_ssh_login_command(
                "ssh -p 12345 root@example.com rm -rf /"
            )

    def test_reads_reference_metadata_over_existing_sftp_session(self) -> None:
        connection = AutoDLTTSConnection()
        client = Mock()
        client.get_transport.return_value.is_active.return_value = True
        sftp = client.open_sftp.return_value
        sftp.listdir.return_value = ["asr.txt", "ref.mp3"]
        transcript_file = sftp.open.return_value
        transcript_file.read.return_value = "台詞".encode("utf-8")
        connection._client = client

        self.assertEqual(
            connection.read_reference_metadata(
                "/root/reference_voices",
                "平静",
            ),
            (
                "/root/reference_voices/平静/ref.mp3",
                "台詞",
            ),
        )
        sftp.close.assert_called_once_with()

    def test_stop_interrupts_remote_foreground_process(self) -> None:
        connection = AutoDLTTSConnection()
        channel = Mock()
        channel.closed = False
        connection._channel = channel

        connection.stop()

        channel.send.assert_called_once_with(b"\x03")
        channel.close.assert_called_once_with()

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI is required")
    def test_password_round_trip_uses_windows_dpapi(self) -> None:
        token = protect_secret("temporary-password")
        self.assertNotIn("temporary-password", token)
        self.assertEqual(
            unprotect_secret(token),
            "temporary-password",
        )

    @unittest.skipUnless(sys.platform == "darwin", "macOS Keychain is required")
    def test_password_round_trip_uses_macos_keychain(self) -> None:
        saved = Mock(returncode=0, stdout="", stderr="")
        loaded = Mock(returncode=0, stdout="temporary-password\n", stderr="")
        with patch(
            "tool.credentials.subprocess.run",
            side_effect=[saved, loaded],
        ) as run:
            token = protect_secret("temporary-password")
            password = unprotect_secret(token)

        self.assertEqual(token, "keychain:AutoDL")
        self.assertNotIn("temporary-password", token)
        self.assertEqual(password, "temporary-password")
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
