#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/bootstrap-host.sh <ssh-cidr>[,<ssh-cidr>...]" >&2
  exit 1
fi

ssh_cidrs=${1:-}
if [[ -z ${ssh_cidrs} ]]; then
  echo "At least one explicit SSH CIDR is required; no permissive default is provided." >&2
  exit 1
fi

IFS=',' read -r -a cidrs <<<"${ssh_cidrs}"
for cidr in "${cidrs[@]}"; do
  if [[ ! ${cidr} =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/(3[0-2]|[12]?[0-9])$ ]]; then
    echo "Invalid IPv4 CIDR: ${cidr}" >&2
    exit 1
  fi
done

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl docker.io docker-compose-v2 fail2ban postgresql-client ufw unattended-upgrades

install -d -m 0755 /etc/ssh/sshd_config.d
install -m 0600 /dev/null /etc/ssh/sshd_config.d/60-fido-hardening.conf
cat >/etc/ssh/sshd_config.d/60-fido-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers ubuntu
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no
X11Forwarding no
EOF
sshd -t
systemctl reload ssh

install -d -m 0755 /etc/fail2ban/jail.d
cat >/etc/fail2ban/jail.d/fido-sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban docker unattended-upgrades

ufw default deny incoming
ufw default allow outgoing
ufw allow 80/tcp comment 'Fido HTTP ACME redirect'
ufw allow 443/tcp comment 'Fido HTTPS origin'
for cidr in "${cidrs[@]}"; do
  ufw allow from "${cidr}" to any port 22 proto tcp comment 'Fido restricted SSH'
done
ufw --force enable

install -d -m 0700 -o root -g root /etc/fido
if [[ -f /etc/fido/fido.env ]]; then
  chown root:root /etc/fido/fido.env
  chmod 0600 /etc/fido/fido.env
fi
install -d -m 0755 -o root -g root /opt/fido/releases
usermod -aG docker ubuntu

echo "Host hardening complete. Reconnect before closing the current SSH session and verify every intended SSH source CIDR." >&2
