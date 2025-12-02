# Systemd configuration validation

Use the `validate-systemd` subcommand to sanity-check systemd unit files and DNS resolver configuration.

```bash
sudo automatic_linux_network_repair validate-systemd --path /etc/systemd
```

The command performs three steps:

1. **Tool detection** – Confirms `systemctl` and `systemd-analyze` are available. If either is missing, the command logs a warning and returns a non-zero exit code so you can surface the dependency in CI or provisioning scripts.
2. **`resolved.conf` linting** – Parses `resolved.conf` under the provided path and reports invalid IP addresses, unsupported option values (e.g., `DNSSEC` or `DNSOverTLS`), and empty DNS lists that cannot resolve a known host.
3. **Unit verification** – Recurses through the systemd tree looking for unit-like files (`.service`, `.socket`, `.target`, `.network`, etc.) and runs `systemd-analyze verify` against each. Each result is reported as `[OK]` or `[FAIL]` with stderr/stdout details.

Exit codes:

- `0` – All validations passed.
- `1` – Missing tools, no unit files found when config issues exist, or one or more units/resolver settings failed validation.

Provide `--path` to point at an alternate root (for example, a mounted target filesystem or chroot). The summary output includes the number of files inspected and the count of failures to make it easy to grep or script against.
