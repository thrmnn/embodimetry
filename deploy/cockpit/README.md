# Cockpit deployment

Current serving (2026-08-11): laptop builds `_hub/_stage/` and rsyncs to
`hetzner:/srv/cockpit/current/`; nginx (`nginx-cockpit.conf`) serves it on
`127.0.0.1:8080`; a Tailscale sidecar node fronts it at
`https://embodimetry.tail489c2e.ts.net/_hub/` (canonical), with the legacy
host mount `https://ubuntu-8gb-hel1-1.tail489c2e.ts.net:8443/_hub/` still up
during transition — both tailnet-only. Push automation:
`cockpit-push.{service,timer}` (laptop, systemd user units). Never run
`tailscale serve reset` on the VPS — the other serve mounts (443→BRISAverse,
8737→mirante, 8747→varanda) are live apps.

## Tailscale sidecar node (own hostname for the PWA) — LIVE

**Why.** The VPS hostname hosts four PWAs on different ports (443 BRISAverse,
8737 mirante, 8747 varanda, 8443 cockpit). Ports make them distinct origins
per spec, but tailnet-private PWAs can't be minted as WebAPKs (Google's
minting service can't fetch a private manifest), so Android Chrome falls back
to shortcut installs whose installed-app matching is host-keyed in practice —
installing the cockpit collided with varanda. A distinct *hostname* fixes the
identity under every matching scheme and moves the cockpit to default
port 443.

**Deployed.** The `ts-embodimetry` docker sidecar (userspace networking,
`--network=host`, state in the `ts-embodimetry-state` volume) joins the
tailnet as node `embodimetry` and runs
`tailscale serve --bg --https=443 http://127.0.0.1:8080`. Same nginx root,
same push pipeline; manifest `id` is origin-relative so it needed no edit.
Verify any time:

```sh
curl -so /dev/null -w '%{http_code}' https://embodimetry.tail489c2e.ts.net/_hub/
# expect: 200
```

**Key expiry** is disabled on the online nodes, so neither the sidecar nor
the VPS drops off the tailnet on key rotation day.

**Laptop availability caveat.** A Windows logon task starts WSL (and thus the
push units) on the MSI laptop, but it is interactive-only: an unattended
reboot leaves WSL — and the cockpit push pipeline — down until someone logs
in. The VPS keeps serving the last-pushed build regardless; only freshness
suffers.

**Retire the legacy mount** once the tablet install is repointed
(rollback for the sidecar itself: `docker rm -f ts-embodimetry` — the 8443
mount is untouched):

```sh
tailscale serve --https=8443 off
```

**Related, separate:** mirante/varanda/BRISAverse all ship manifests with no
`"id"` and scope `/` — they will collide with *each other* the same way;
adding distinct `id` fields in their own repos is worth doing regardless.
