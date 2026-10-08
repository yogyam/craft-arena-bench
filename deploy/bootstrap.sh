#!/usr/bin/env bash
# Sets up the public arena server on Ubuntu 24.04 (arm64 or amd64). Idempotent. Run as root.
set -euo pipefail

PAPER_VERSION="26.1.2"
PAPER_BUILD="74"
PAPER_SHA256="1d70b1dab9cf4a6de615209a536f3a45a2186240253c428213ce2188ab95e5f7"
VELOCITY_VERSION="4.2.0"
VELOCITY_BUILD="30 velocity-4.2.0-30.jar 35a5596a5468a035d8a32c8de5ebb0dc6b8d8f0cc3ff5169d514aca762af8aa8 https://fill-data.papermc.io/v1/objects/35a5596a5468a035d8a32c8de5ebb0dc6b8d8f0cc3ff5169d514aca762af8aa8/velocity-4.2.0-30.jar"
VELOCITY_SHA256=""
UA="craft-arena-bench-deploy (https://github.com/yogyam/craft-arena-bench)"
ROOT=/opt/arena

echo "== packages"
apt-get update -qq
apt-get install -y -qq wget gnupg ca-certificates ufw git python3-venv nodejs npm >/dev/null
if ! command -v java >/dev/null || ! java -version 2>&1 | grep -q '"25'; then
  wget -qO- https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor -o /etc/apt/keyrings/adoptium.gpg
  echo "deb [signed-by=/etc/apt/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb $(. /etc/os-release; echo $VERSION_CODENAME) main" > /etc/apt/sources.list.d/adoptium.list
  apt-get update -qq && apt-get install -y -qq temurin-25-jdk >/dev/null
fi
java -version 2>&1 | head -1

echo "== user and folders"
id arena >/dev/null 2>&1 || useradd --system --create-home --home-dir "$ROOT" --shell /usr/sbin/nologin arena
mkdir -p "$ROOT"/{velocity,paper,secrets,results}
chmod 700 "$ROOT/secrets"

echo "== secrets (generated once)"
[ -s "$ROOT/secrets/rcon_password" ] || head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 40 > "$ROOT/secrets/rcon_password"
[ -s "$ROOT/secrets/forwarding.secret" ] || head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 40 > "$ROOT/secrets/forwarding.secret"
chmod 600 "$ROOT"/secrets/*
RCON_PASSWORD=$(cat "$ROOT/secrets/rcon_password")
FORWARDING_SECRET=$(cat "$ROOT/secrets/forwarding.secret")

fetch() {  # url sha256 dest
  if [ -f "$3" ] && echo "$2  $3" | sha256sum -c --quiet 2>/dev/null; then return; fi
  wget -q --header="User-Agent: $UA" -O "$3.part" "$1"
  echo "$2  $3.part" | sha256sum -c --quiet
  mv "$3.part" "$3"
}
echo "== jars"
PAPER_URL=$(wget -qO- --header="User-Agent: $UA" "https://fill.papermc.io/v3/projects/paper/versions/$PAPER_VERSION/builds" | python3 -c "import json,sys; print(next(b for b in json.load(sys.stdin) if b['id']==$PAPER_BUILD)['downloads']['server:default']['url'])")
fetch "$PAPER_URL" "$PAPER_SHA256" "$ROOT/paper/paper.jar"
VELOCITY_URL=$(wget -qO- --header="User-Agent: $UA" "https://fill.papermc.io/v3/projects/velocity/versions/$VELOCITY_VERSION/builds" | python3 -c "import json,sys; print(next(b for b in json.load(sys.stdin) if b['id']==$VELOCITY_BUILD)['downloads']['server:default']['url'])")
fetch "$VELOCITY_URL" "$VELOCITY_SHA256" "$ROOT/velocity/velocity.jar"

echo "== configs"
cp "$(dirname "$0")/velocity.toml" "$ROOT/velocity/velocity.toml"
printf '%s' "$FORWARDING_SECRET" > "$ROOT/velocity/forwarding.secret"
chmod 600 "$ROOT/velocity/forwarding.secret"
sed "s/__RCON_PASSWORD__/$RCON_PASSWORD/" "$(dirname "$0")/paper.server.properties" > "$ROOT/paper/server.properties"
echo "eula=true" > "$ROOT/paper/eula.txt"
mkdir -p "$ROOT/paper/config"
sed "s/__FORWARDING_SECRET__/$FORWARDING_SECRET/" "$(dirname "$0")/paper-global.yml" > "$ROOT/paper/config/paper-global.yml"
chown -R arena:arena "$ROOT"
chmod 600 "$ROOT/paper/server.properties" "$ROOT/paper/config/paper-global.yml"

echo "== services (heaps sized from memory)"
MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$MEM_MB" -ge 12000 ]; then PAPER_XMX=6G; PAPER_XMS=4G; VELOCITY_XMX=1G
elif [ "$MEM_MB" -ge 3500 ]; then PAPER_XMX=2200M; PAPER_XMS=1G; VELOCITY_XMX=384M
else PAPER_XMX=1100M; PAPER_XMS=512M; VELOCITY_XMX=192M; fi
echo "memory ${MEM_MB} MB: paper -Xmx$PAPER_XMX, velocity -Xmx$VELOCITY_XMX"
for unit in "$(dirname "$0")"/systemd/*.service; do
  sed -e "s/__PAPER_XMS__/$PAPER_XMS/; s/__PAPER_XMX__/$PAPER_XMX/; s/__VELOCITY_XMX__/$VELOCITY_XMX/" "$unit" > "/etc/systemd/system/$(basename "$unit")"
done
systemctl daemon-reload
systemctl enable --now paper velocity

echo "== firewall: 22 and 25565 only"
# Oracle's Ubuntu images ship iptables rules that reject everything but SSH and re-apply them at boot. Clear them so ufw is the one firewall.
if [ -f /etc/iptables/rules.v4 ]; then
  iptables -F INPUT 2>/dev/null || true
  systemctl disable --now netfilter-persistent >/dev/null 2>&1 || true
  mv /etc/iptables/rules.v4 /etc/iptables/rules.v4.oracle-default 2>/dev/null || true
fi
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow 22/tcp >/dev/null
ufw allow 25565/tcp >/dev/null
ufw --force enable >/dev/null
ufw status | sed -n '1,6p'

echo "== done. Paper log: journalctl -u paper -f ; Velocity log: journalctl -u velocity -f"
