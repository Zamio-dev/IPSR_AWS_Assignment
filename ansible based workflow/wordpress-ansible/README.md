# WordPress on RHEL 10 — Full Ansible Automation
### AWS EC2 t2.micro | MariaDB 10.6 | PHP 8.3 | Nginx | Let's Encrypt SSL | WP-CLI

---

## Project Overview

This Ansible project fully automates the deployment of a production-grade WordPress website on a **Red Hat Enterprise Linux 10** EC2 instance. Every step from package installation through SSL issuance and blog post creation is handled automatically — no manual SSH required after setup.

---

## Project Structure

```
wordpress-ansible/
├── ansible.cfg                         # Ansible runtime configuration
├── site.yml                            # ★ MASTER PLAYBOOK — run this
├── verify.yml                          # Post-deploy verification checks
├── rollback.yml                        # Complete teardown/rollback
├── requirements.yml                    # Galaxy collection dependencies
│
├── inventory/
│   └── hosts.ini                       # Your EC2 host + SSH key
│
├── group_vars/
│   └── all.yml                         # ★ ALL VARIABLES — edit this first
│
└── roles/
    ├── 01_common/                      # System baseline (swap, repos, SELinux, firewall)
    ├── 02_mariadb/                     # MariaDB 10.6 install + DB/user creation
    ├── 03_php/                         # PHP 8.3 + extensions + PHP-FPM pool
    ├── 04_nginx/                       # Nginx install + server blocks (templates)
    ├── 05_user_sftp/                   # Linux user + /home/user/site/public + SFTP chroot
    ├── 06_wordpress/                   # WP download + WP-CLI install + blog post
    ├── 07_phpmyadmin/                  # phpMyAdmin + basic auth + Nginx config
    └── 08_ssl/                         # Certbot Let's Encrypt + auto-renewal cron
```

---

## Prerequisites

### 1. Local Machine Requirements

```bash
# Install Ansible (Python 3.9+ required)
pip3 install ansible

# Verify version (must be 2.14+)
ansible --version

# Install required Ansible Galaxy collections
ansible-galaxy collection install -r requirements.yml
```

### 2. AWS EC2 Instance

- **AMI:** Red Hat Enterprise Linux 10 (64-bit x86)
- **Instance Type:** `t2.micro`
- **Key Pair:** Download `.pem` file, set permissions: `chmod 400 your-key.pem`
- **Security Group Inbound Rules:**

| Port | Protocol | Source     | Purpose              |
|------|----------|------------|----------------------|
| 22   | TCP      | Your IP    | SSH + SFTP           |
| 80   | TCP      | 0.0.0.0/0  | HTTP (ACME challenge) |
| 443  | TCP      | 0.0.0.0/0  | HTTPS (WordPress)    |
| 8080 | TCP      | Your IP    | phpMyAdmin           |

### 3. Domain Name

- You must have a registered domain
- Set an **A record** pointing to your EC2 public IP **before** running the playbook
- Without a valid DNS record, Certbot SSL issuance will fail

---

## Quick Start

### Step 1 — Clone / Extract the Project

```bash
cd ~
unzip wordpress-ansible.zip   # or extract the tarball
cd wordpress-ansible
```

### Step 2 — Configure Your Variables and Load Secrets

1. Copy the sample env file and fill in your real passwords:
```bash
cp .env.sample .env
nano .env          # replace every CHANGE_ME with a strong password
```

2. Source the `.env` file so Ansible can read the exported variables:
```bash
set -a; source .env; set -a
```

3. Open `group_vars/all.yml` — passwords are now imported from `.env`, so you only need to set domain, emails, and site names (not passwords).

```yaml
# group_vars/all.yml — ONLY edit non-password values here
# Passwords are sourced from .env (see README)
wp_user_password:     "CHANGE_ME"     # overwritten by .env
db_root_password:     "CHANGE_ME"     # overwritten by .env
db_password:          "CHANGE_ME"     # overwritten by .env
wp_admin_password:    "CHANGE_ME"     # overwritten by .env
pma_htpasswd_password:"CHANGE_ME"     # overwritten by .env

### Step 3 — Configure Inventory

Open `inventory/hosts.ini` and update:

```ini
[wordpress_servers]
wordpress-server ansible_host=1.2.3.4 ansible_user=ec2-user ansible_ssh_private_key_file=~/.ssh/your-key.pem
```

Replace:
- `1.2.3.4` → your EC2 public IP
- `~/.ssh/your-key.pem` → path to your downloaded key pair

### Step 4 — Test Connectivity

```bash
ansible all -i inventory/hosts.ini -m ping
```

Expected output:
```
wordpress-server | SUCCESS => {
    "ping": "pong"
}
```

### Step 5 — Run the Full Playbook

```bash
ansible-playbook -i inventory/hosts.ini site.yml
```

**Expected runtime:** 10–20 minutes on a t2.micro instance.

---

## What the Playbook Does (Role by Role)

| # | Role | What it Automates |
|---|------|-------------------|
| 01 | `common` | Hostname, timezone, system update, EPEL/Remi repos, 2 GB swap, SELinux booleans, firewall rules |
| 02 | `mariadb` | MariaDB 10.6 repo + install, secure installation, create DB `myblog_db`, create DB user |
| 03 | `php` | PHP 8.3 via Remi, all WP extensions (mysqlnd, gd, curl, zip, mbstring…), dedicated PHP-FPM pool per user |
| 04 | `nginx` | Nginx install, WordPress server block (HTTP→HTTPS redirect, PHP-FPM socket, security headers), phpMyAdmin server block on port 8080 |
| 05 | `user_sftp` | Create Linux user with home at `/home/bloguser`, create `/home/bloguser/myblog/public`, SFTP chroot jail via `sshd_config` Match Group block |
| 06 | `wordpress` | Download latest WP, extract to `site_root`, deploy `wp-config.php` with live salt keys, WP-CLI install, run web installer, set permalinks, create pages, write personal blog post, install Yoast/Wordfence/WP Super Cache plugins |
| 07 | `phpmyadmin` | Auto-detect latest PMA version, download + deploy to `/usr/share/phpmyadmin`, generate blowfish secret, set up Nginx basic auth (`.htpasswd`) |
| 08 | `ssl` | Certbot + python3-certbot-nginx, DNS pre-flight check, issue Let's Encrypt cert, deploy SSL Nginx config, update WordPress URLs to HTTPS, set up auto-renewal cron |

---

## Run Individual Roles (Using Tags)

```bash
# Run only MariaDB setup
ansible-playbook -i inventory/hosts.ini site.yml --tags mariadb

# Run only PHP + Nginx
ansible-playbook -i inventory/hosts.ini site.yml --tags "php,nginx"

# Run only SSL issuance
ansible-playbook -i inventory/hosts.ini site.yml --tags ssl

# Run everything EXCEPT SSL (useful if domain isn't ready)
ansible-playbook -i inventory/hosts.ini site.yml --skip-tags ssl

# Start from a specific task
ansible-playbook -i inventory/hosts.ini site.yml --start-at-task "WORDPRESS | Run WordPress installation via WP-CLI"
```

---

## Verify the Deployment

After `site.yml` completes, run the verification playbook:

```bash
ansible-playbook -i inventory/hosts.ini verify.yml
```

This checks:
- ✅ Nginx, PHP-FPM, MariaDB all running
- ✅ PHP version is 8.x
- ✅ MariaDB version is 10.6
- ✅ SSL certificate file exists
- ✅ `wp-config.php` deployed at correct path
- ✅ phpMyAdmin installed
- ✅ SFTP user exists
- ✅ Nginx config syntax valid
- ✅ WordPress DB connectivity
- ✅ HTTPS site responding

---

## Credentials After Deployment

The master playbook prints a credentials summary at the end. Here is the template:

```
SFTP Credentials:
  Host     : <EC2_PUBLIC_IP>
  Port     : 22
  Protocol : SFTP
  Username : bloguser
  Password : (from .env → WP_USER_PASSWORD)
  Path     : /myblog/public  (chrooted to /home/bloguser)

phpMyAdmin Credentials:
  URL              : http://yourdomain.com:8080
  Basic Auth User  : pmaadmin
  Basic Auth Pass  : (from .env → PMA_HTPASSWD_PASSWORD)
  DB Username      : myblog_user
  DB Password      : (from .env → DB_PASSWORD)

WordPress Credentials:
  Admin URL : https://yourdomain.com/wp-admin
  Username  : wpadmin
  Password  : (from .env → WP_ADMIN_PASSWORD)
```

---

## Connecting via SFTP

**FileZilla:**
1. Open FileZilla → File → Site Manager → New Site
2. Protocol: `SFTP`
3. Host: `<EC2_PUBLIC_IP>`, Port: `22`
4. Logon Type: `Normal`
5. User: `bloguser`, Password: (your `WP_USER_PASSWORD` from `.env`)
6. Click Connect

**Command Line:**
```bash
sftp bloguser@<EC2_PUBLIC_IP>
# After login:
sftp> cd /myblog/public
sftp> ls
```

---

## Rollback / Teardown

To completely remove everything:

```bash
ansible-playbook -i inventory/hosts.ini rollback.yml
```

You will be prompted to type `YES` to confirm. This removes:
- Website user and `/home/bloguser/`
- MariaDB database and user
- SSL certificate
- Nginx configs for the site + phpMyAdmin
- PHP-FPM pool config
- phpMyAdmin files
- WP-CLI binary

---

## Troubleshooting

### Ping fails
```bash
# Check key permissions
chmod 400 ~/.ssh/your-key.pem
# Check security group allows port 22 from your IP
```

### Task fails with "MODULE FAILURE"
```bash
# Ensure Galaxy collections are installed
ansible-galaxy collection install -r requirements.yml
```

### Certbot fails
```bash
# Verify DNS resolves to your server
dig +short yourdomain.com
# Must match EC2 public IP exactly
```

### Nginx 502 Bad Gateway
```bash
# Check PHP-FPM socket exists
ssh ec2-user@<IP> "ls -la /var/run/php-fpm/"
# Check PHP-FPM is running
ssh ec2-user@<IP> "sudo systemctl status php-fpm"
```

### WordPress "Error establishing database connection"
```bash
# Verify DB credentials in group_vars/all.yml match what was created
ssh ec2-user@<IP> "sudo mysql -u myblog_user -p myblog_db -e 'SELECT 1'"
```

### SELinux denying access
```bash
# Check SELinux audit log
ssh ec2-user@<IP> "sudo ausearch -m avc -ts recent"
# Re-run common role to reapply booleans
ansible-playbook -i inventory/hosts.ini site.yml --tags common
```

---

## Security Notes

> **Security hint:** Passwords live in `.env` (gitignored). Never commit `.env`. All real values should be stored only there.
- `DISALLOW_FILE_EDIT` is set to `true` in `wp-config.php` to block the theme/plugin editor
- phpMyAdmin is behind both Nginx basic auth AND requires a valid DB credential
- phpMyAdmin port (8080) should be restricted to your IP in AWS Security Group
- Let's Encrypt certificates auto-renew via cron every day at 03:00
- SFTP users are chrooted to their own `/home/username` — they cannot browse the rest of the filesystem

---

*Ansible Project v1.0 | RHEL 10 | MariaDB 10.6 | PHP 8.3 | Nginx | Let's Encrypt | WordPress + WP-CLI*
