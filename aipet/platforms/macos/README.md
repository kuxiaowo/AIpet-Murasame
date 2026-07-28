# macOS adapter placeholder

This directory intentionally contains no macOS implementation yet.

Implement `create_runtime()` by satisfying the focused contracts in
`aipet.platforms.contracts`:

- paths and managed-model locations;
- Qt/native window integration and fullscreen behavior;
- idle-time reporting and the global voice shortcut;
- Keychain-backed credential storage;
- subprocess lifecycle, log viewing, and GPT-SoVITS runtime discovery;
- archive-tool discovery and audio-device ordering.

Do not add operating-system branches to `aipet.core` or `aipet.ui`. Platform
code must remain inside this directory and be exposed through
`PlatformRuntime`.
