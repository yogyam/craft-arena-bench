# The arena machine on AWS, as code. One Graviton (ARM) instance, a fixed public address, a firewall that admits
# SSH from one address and Minecraft from anywhere, and a first boot that clones the repository and runs
# deploy/bootstrap.sh. Apply with OpenTofu or Terraform:
#
#   cd deploy/aws
#   tofu init
#   tofu apply -var ssh_cidr=$(curl -s https://api.ipify.org)/32 -var alert_email=you@example.org
#
# Credentials come from the AWS CLI's configuration (aws configure); nothing is stored here.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  description = "AWS region; pick one near the players"
  type        = string
  default     = "us-west-2"
}

variable "instance_type" {
  description = "Graviton instance. t4g.small (2 vCPU, 2 GB) fits a $30 monthly line; t4g.medium (4 GB) is roomier at about $31 all-in"
  type        = string
  default     = "t4g.small"
}

variable "ssh_cidr" {
  description = "Who may SSH in, as a CIDR. Your own public address with /32; change with -var when you move networks"
  type        = string
}

variable "ssh_public_key_path" {
  description = "The public key that may log in as ubuntu"
  type        = string
  default     = "~/.ssh/arena_ed25519.pub"
}

variable "repository" {
  description = "The repository the machine clones on first boot to get deploy/bootstrap.sh"
  type        = string
  default     = "https://github.com/yogyam/craft-arena-bench.git"
}

# Canonical's current Ubuntu 24.04 image for ARM.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_vpc" "default" {
  default = true
}

resource "aws_key_pair" "arena" {
  key_name   = "craft-arena"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_security_group" "arena" {
  name        = "craft-arena"
  description = "SSH from the maintainer, Minecraft from anywhere, nothing else"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from the maintainer only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }
  ingress {
    description      = "Minecraft (Velocity) from anywhere"
    from_port        = 25565
    to_port          = 25565
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

resource "aws_instance" "arena" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.arena.key_name
  vpc_security_group_ids = [aws_security_group.arena.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  # No IAM role: the machine holds no cloud credentials. IMDSv2 only.
  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  # First boot: get the deploy folder from the repository and run the bootstrap. Everything after that is systemd.
  user_data = <<-CLOUDINIT
    #!/bin/bash
    set -euo pipefail
    apt-get update -qq && apt-get install -y -qq git >/dev/null
    git clone --depth 1 ${var.repository} /opt/craft-arena-bench-deploy
    bash /opt/craft-arena-bench-deploy/deploy/bootstrap.sh 2>&1 | tee /var/log/arena-bootstrap.log
  CLOUDINIT

  tags = {
    Name    = "craft-arena"
    Project = "craft-arena-bench"
  }
}

resource "aws_eip" "arena" {
  instance = aws_instance.arena.id
  domain   = "vpc"
  tags     = { Name = "craft-arena" }
}

output "public_ip" {
  value = aws_eip.arena.public_ip
}

output "ssh" {
  value = "ssh -i ~/.ssh/arena_ed25519 ubuntu@${aws_eip.arena.public_ip}"
}

output "minecraft" {
  value = "${aws_eip.arena.public_ip}:25565"
}
