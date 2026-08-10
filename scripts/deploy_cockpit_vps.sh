#!/usr/bin/env bash
# Idempotent VPS provisioning for the cockpit serving layer (deploy/cockpit/).
# The VPS hosts other live services and tailscale serve already carries other
# mounts (443->8770, 8737, 8747) — this script only ADDS the :8443 mount and
# never runs `tailscale serve reset`.
#
# Rollback:
#   content:  git checkout <sha> && scripts/push_cockpit.sh
#   serving:  ssh hetzner 'sudo tailscale serve --https=8443 off'
#   laptop:   systemctl --user disable --now cockpit-push.timer
set -euo pipefail
HOST="${1:-hetzner}"
cd "$(dirname "$0")/.."
scp deploy/cockpit/nginx-cockpit.conf "$HOST:/tmp/nginx-cockpit.conf"
ssh "$HOST" bash -s <<'EOF'
set -euo pipefail
sudo mkdir -p /srv/cockpit/current
sudo chown -R "$USER" /srv/cockpit
sudo chmod o+rx /srv/cockpit /srv/cockpit/current
sudo install -m 644 /tmp/nginx-cockpit.conf /etc/nginx/sites-available/cockpit
sudo ln -sfn ../sites-available/cockpit /etc/nginx/sites-enabled/cockpit
# stock default site would bind public :80 the moment nginx starts; the
# cockpit is loopback-only, so drop the symlink (sites-available copy stays)
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
tailscale serve status | grep -q ':8443' || \
  sudo tailscale serve --bg --https=8443 http://127.0.0.1:8080
EOF
