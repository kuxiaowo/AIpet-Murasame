# Bundled 7-Zip extractor

AIpet includes the unmodified `7zr.exe` command-line extractor from the
7-Zip LZMA SDK so that managed GPT-SoVITS packages can be installed without a
separate system-wide 7-Zip installation.

- Component: `7zr.exe`
- Version: 7-Zip/LZMA SDK 26.02 (2026-06-25)
- Architecture: Windows x86 (runs on supported Windows x64 systems)
- Upstream: https://www.7-zip.org/sdk.html
- Release asset:
  https://github.com/ip7z/7zip/releases/download/26.02/7zr.exe
- SHA-256:
  `56b8cc9f4971cef253644fafe54063ed7fdca551d4dee0f8c6baa81b855acd72`

The 7-Zip project states that the LZMA SDK, which includes `7zr.exe`, is in the
public domain. AIpet does not modify the executable. Source and current license
information are available from the upstream LZMA SDK page linked above.

When updating this component, update the pinned SHA-256 value in
`packaging/build_exe.ps1`, run the download-manager tests, and rebuild both
Windows executables.
