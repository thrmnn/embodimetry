# Cockpit deployment

Current serving (2026-08-10): laptop builds `_hub/_stage/` and rsyncs to
`hetzner:/srv/cockpit/current/`; nginx (`nginx-cockpit.conf`) serves it on
`127.0.0.1:8080`; `tailscale serve --bg --https=8443 http://127.0.0.1:8080`
fronts it at `https://ubuntu-8gb-hel1-1.tail489c2e.ts.net:8443/_hub/`,
tailnet-only. Push automation: `cockpit-push.{service,timer}` (laptop, systemd
user units). Never run `tailscale serve reset` on the VPS — the other serve
mounts (443→BRISAverse, 8737→mirante, 8747→varanda) are live apps.

## Deferred: Tailscale sidecar node (own hostname for the PWA)

**Why (documented 2026-08-10, not yet built).** The VPS hostname hosts four
PWAs on different ports (443 BRISAverse, 8737 mirante, 8747 varanda, 8443
cockpit). Ports make them distinct origins per spec, but tailnet-private PWAs
can't be minted as WebAPKs (Google's minting service can't fetch a private
manifest), so Android Chrome falls back to shortcut installs whose
installed-app matching is host-keyed in practice — installing the cockpit
collides with varanda. A distinct *hostname* fixes the identity under every
matching scheme and moves the cockpit to default port 443.

**Plan.**

1. Théo: Tailscale admin console → Settings → Keys → *Generate auth key*
   (single-use is fine). Also disable key expiry for the new node afterwards.
2. VPS — sidecar joins the tailnet as its own node named `embodimetry`,
   sharing the host network so it can reach nginx on loopback; userspace
   networking avoids any tun/tailscaled conflict with the host daemon:

   ```sh
   docker run -d --name ts-embodimetry --restart unless-stopped \
     --network=host \
     -e TS_AUTHKEY=<key> -e TS_HOSTNAME=embodimetry -e TS_USERSPACE=1 \
     -e TS_STATE_DIR=/var/lib/tailscale \
     -v ts-embodimetry-state:/var/lib/tailscale \
     tailscale/tailscale
   docker exec ts-embodimetry tailscale serve --bg --https=443 http://127.0.0.1:8080
   ```

3. Verify `https://embodimetry.tail489c2e.ts.net/_hub/` → 200 with the same
   headers as the 8443 mount, then re-run the installability audit (headless
   Chromium CDP `Page.getInstallabilityErrors`, see the session notes /
   `git log 67bada3` for the snippet) and an offline-reload test.
4. Nothing else changes: same nginx root, same push pipeline, manifest `id`
   is origin-relative so it needs no edit. Update the URL in memory, the
   fleet report, and the tablet install.
5. Keep the 8443 mount up during transition (`tailscale serve --https=8443
   off` to retire it later). Rollback: `docker rm -f ts-embodimetry` — the
   8443 mount is untouched.

**Related, separate:** mirante/varanda/BRISAverse all ship manifests with no
`"id"` and scope `/` — they will collide with *each other* the same way;
adding distinct `id` fields in their own repos is worth doing regardless.
