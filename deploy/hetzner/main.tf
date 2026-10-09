# The arena machine on Hetzner Cloud, as code. One ARM server (CAX11: 2 cores, 4 GB, about 4 euros a month), a
# firewall that admits SSH from one address and Minecraft from anywhere, and a first boot that clones the
# repository and runs deploy/bootstrap.sh.
#
#   export HCLOUD_TOKEN=...            # an API token from the Hetzner Cloud console, read-and-write
#   cd deploy/hetzner && tofu init
#   tofu apply -var ssh_cidr=$(curl -s https://api.ipify.org)/32

terraform {
  required_version = ">= 1.6"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.50"
    }
  }
}

provider "hcloud" {}

variable "location" {
  description = "Hetzner location: ash (Ashburn, US east), hil (Hillsboro, US west), fsn1 / nbg1 / hel1 (Europe)"
  type        = string
  default     = "hil"
}

variable "server_type" {
  description = "cax11 (2 ARM cores, 4 GB) is enough; cax21 (4 cores, 8 GB) if the arena grows"
  type        = string
  default     = "cax11"
}

variable "ssh_cidr" {
  description = "Who may SSH in, as a CIDR. Your own public address with /32"
  type        = string
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/arena_ed25519.pub"
}

variable "repository" {
  type    = string
  default = "https://github.com/yogyam/craft-arena-bench.git"
}

resource "hcloud_ssh_key" "arena" {
  name       = "craft-arena"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "hcloud_firewall" "arena" {
  name = "craft-arena"
  rule {
    description = "SSH from the maintainer only"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = [var.ssh_cidr]
  }
  rule {
    description = "Minecraft (Velocity) from anywhere"
    direction   = "in"
    protocol    = "tcp"
    port        = "25565"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "arena" {
  name         = "craft-arena"
  image        = "ubuntu-24.04"
  server_type  = var.server_type
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.arena.id]
  firewall_ids = [hcloud_firewall.arena.id]
  labels       = { project = "craft-arena-bench" }

  user_data = <<-CLOUDINIT
    #!/bin/bash
    set -euo pipefail
    apt-get update -qq && apt-get install -y -qq git >/dev/null
    git clone --depth 1 ${var.repository} /opt/craft-arena-bench-deploy
    bash /opt/craft-arena-bench-deploy/deploy/bootstrap.sh 2>&1 | tee /var/log/arena-bootstrap.log
  CLOUDINIT
}

output "public_ip" {
  value = hcloud_server.arena.ipv4_address
}

output "ssh" {
  value = "ssh -i ~/.ssh/arena_ed25519 root@${hcloud_server.arena.ipv4_address}"
}

output "minecraft" {
  value = "${hcloud_server.arena.ipv4_address}:25565"
}
