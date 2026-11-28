# Shared LAN certificate

- [Shared LAN certificate](#shared-lan-certificate)
  - [Verification](#verification)

Both build modes capture one custom CA as `lan.crt`. Base installs it and npm inherits it. Release settings, certificate fingerprints, tests, and documentation use the single input.

## Verification

Offline release validation and 13 focused certificate, snapshot, and relative-path tests passed. No native build or publication was run.
