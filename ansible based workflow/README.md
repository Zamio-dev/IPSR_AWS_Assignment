# WordPress on RHEL 10 — Fully Automated with Ansible

A hands-free WordPress deployment that takes a bare EC2 instance and turns it into a production-ready blog — down to the final blog post.

---

## At a Glance

This project automates an entire web stack onto a single, small EC2 instance (`t2.micro`). Everything happens via Ansible — no manual SSH, no copy-pasting commands, no human error. You start with a Red Hat EC2 and end with:

- A live WordPress site under HTTPS
- phpMyAdmin accessible on a restricted port
- SFTP access for file uploads, chrooted and jailed
- A Let's Encrypt SSL certificate with automatic renewal
- SELinux hardened, firewall rules configured
- A personal blog post already written and published

---

## What You Get After Running the Playbook

A fully operational blog with these credentials delivered back to your terminal:

| Service | URL | Login |
|---|---|---|
| **WordPress** | `https://yourdomain.com/wp-admin` | Admin user from `all.yml` |
| **phpMyAdmin** | `http://yourdomain.com:8080` | Basic auth + DB credentials |
| **SFTP** | `sftp://ec2-public-ip` | Username + password from `all.yml` |

All configuration lives in one place — `group_vars/all.yml`. Edit it once, run the playbook, and the infrastructure adapts to your values.

---

## The Eight-Step Pipeline (How It Works)

The playbook runs 8 roles in order. Each role handles one part of the stack:

### 1. `01_common` — System Baseline

Sets up the host before anything else touches the web stack:

- Applies the hostname (`wordpress-server`) and timezone (Asia/Kolkata)
- Installs all baseline tools (wget, curl, vim, htop, bind-utils)
- Enables EPEL and Remi repositories (Remi is needed for PHP 8.x on RHEL 9)
- Creates a 2 GB swap file (critical for `t2.micro` which has only 1 GB RAM)
- Configures SELinux booleans (`httpd_read_user_content`, `httpd_enable_homedirs`, etc.)
- Opens firewall ports for HTTP, HTTPS, and phpMyAdmin

### 2. `02_mariadb` — Database Server

Installs and secures MariaDB 10.6:

- Configures the official MariaDB repository
- Installs server + client + Python driver (needed by Ansible's MySQL modules)
- Sets root password, removes anonymous users, drops the `test` database
- Creates the WordPress database (`myblog_db`) and a dedicated DB user

### 3. `03_php` — PHP 8.3 + PHP-FPM

Runs PHP under a dedicated FPM pool rather than the default:

- Installs PHP 8.3 with every extension WordPress needs (mysqlnd, gd, curl, zip, mbstring, opcache, imagick…)
- Disables the default `www` PHP-FPM pool
- Creates a pool **named after the website user** — this means if you deploy multiple sites, each runs under its own Unix user

### 4. `04_nginx` — Web Server

Sets up Nginx with two server blocks:

- **WordPress** (port 443, SSL): HTTP-to-HTTPS redirect, PHP-FPM via Unix socket, security headers (HSTS, X-Frame-Options, Referrer-Policy), WordPress permalinks, blocked `xmlrpc.php`
- **phpMyAdmin** (port 8080): Basic auth via `.htpasswd`, restricted paths blocked

### 5. `05_user_sftp` — User & SFTP

Creates the Linux user and locks down SFTP:

- Creates user (e.g. `bloguser`), sets a password, assigns to `sftpusers` group
- Creates `/home/bloguser/myblog/public` as the web root
- Configures `sshd_config` with a `Match Group sftpusers` block — SFTP users are **chrooted** to `/home/username`. They can browse their own site but nothing on the rest of the server

### 6. `06_wordpress` — WordPress Core

Downloads, installs, and configures WordPress:

- Downloads the latest `.tar.gz` from wordpress.org, extracts it
- Generates 8 security salts live from `api.wordpress.org`
- Deploys `wp-config.php` via Jinja2 template
- Runs `wp core install` via WP-CLI (creates admin user, sets site URL)
- Configures permalinks (`/%postname%/`), timezone (Asia/Kolkata)
- **Cleans up** (removes "Hello World" and "Sample Page")
- **Creates pages** ("About Me", "Contact")
- **Writes a blog post** — a sample post about the author's journey into tech and web development
- **Installs plugins**: Yoast SEO, WP Super Cache, Wordfence

### 7. `07_phpmyadmin` — Database Management

Installs phpMyAdmin with security:

- Fetches the latest version number from `phpmyadmin.net`
- Downloads and deploys it to `/usr/share/phpmyadmin`
- Generates a 32-character blowfish secret for session encryption
- Configures `.htpasswd` with HTTP Basic Auth (username: `pmaadmin`)
- Restricts direct access to `/libraries`, `/templates`, `/setup/lib`

### 8. `08_ssl` — Let's Encrypt Certificate

Issues a real SSL certificate:

- Checks that DNS resolves to your EC2 IP (fails fast if not)
- Temporarily switches Nginx to an HTTP-only config (Certbot ACME challenge needs port 80)
- Runs `certbot certonly --webroot` to issue a certificate for both `yourdomain.com` and `www.yourdomain.com`
- Restores the HTTPS server block
- Updates WordPress `siteurl` and `home` to `https://`
- Sets a daily 03:00 AM renewal cron job (with `--post-hook` to reload Nginx)
- Verifies the certificate file exists and prints the live HTTPS URL

---

## Project Structure

```
wordpress-ansible/
├── ansible.cfg              # Ansible runtime settings (SSH, output, callbacks)
├── site.yml                 # ★ Main playbook — run this to deploy everything
├── verify.yml               # Post-deployment checks (services, versions, URLs)
├── rollback.yml             # Teardown playbook (deletes everything)
├── requirements.yml         # Galaxy collections to install (community.mysql, etc.)
│
├── inventory/
│   └── hosts.ini            # EC2 host + SSH key path
│
├── group_vars/
│   └── all.yml              # ★ All variables in one place — edit this first
│
└── roles/
    ├── 01_common/           # System setup, swap, repos, SELinux, firewall
    ├── 02_mariadb/          # Database install + secure config
    ├── 03_php/              # PHP 8.3 + extensions + PHP-FPM pool
    ├── 04_nginx/            # Nginx + server blocks (templates live here)
    ├── 05_user_sftp/        # Linux user, directories, SFTP chroot
    ├── 06_wordpress/        # WP download, WP-CLI, blog post, plugins
    ├── 07_phpmyadmin/       # phpMyAdmin install + auth
    └── 08_ssl/              # Certbot + SSL + auto-renewal cron
```

---

## Prerequisites

### On your local machine

```bash
pip3 install ansible
ansible-galaxy collection install -r wordpress-ansible/requirements.yml
```

You need Python 3.9+. Verify with `ansible --version`.

### On AWS — an EC2 instance with a domain

- **AMI:** Red Hat Enterprise Linux 10 (x86_64)
- **Type:** `t2.micro` (this is the smallest supported instance)
- **Key pair:** Download the `.pem` file; this is used by Ansible to SSH in
- **Security Group:** Ports 22, 80, 443 must be open. Port 8080 (phpMyAdmin) is recommended locked to your IP

### A registered domain

Your domain's A record must point to the EC2 public IP **before** running the playbook. Certbot will fail otherwise, because it needs to prove you control the domain.

---

## How to Use It

### Quick Start

1. **Edit `group_vars/all.yml`** — fill in your real domain, passwords, and usernames
2. **Edit `inventory/hosts.ini`** — set your EC2 IP and `.pem` path
3. **Test connectivity:** `ansible all -i inventory/hosts.ini -m ping`
4. **Run the playbook:**
   ```bash
   ansible-playbook -i inventory/hosts.ini wordpress-ansible/site.yml
   ```

Expected run time: **10–20 minutes** on a `t2.micro` (most time spent downloading packages).

### Running Specific Parts

Each role is tagged. You can run individual roles:

```bash
# Only database + PHP
ansible-playbook -i inventory/hosts.ini wordpress-ansible/site.yml --tags "mariadb,php"

# Only SSL (useful when the rest already ran)
ansible-playbook -i inventory/hosts.ini wordpress-ansible/site.yml --tags ssl

# Skip SSL (if domain isn't ready yet)
ansible-playbook -i inventory/hosts.ini wordpress-ansible/site.yml --skip-tags ssl
```

### Verifying the Deployment

After `site.yml` finishes, run the verification playbook:

```bash
ansible-playbook -i inventory/hosts.ini wordpress-ansible/verify.yml
```

This checks that Nginx, PHP-FPM, and MariaDB are running, versions are correct, the SSL certificate exists, the database is reachable, and the HTTPS site responds.

### Rolling Back

To tear down the entire WordPress stack (destructive — deletes everything):

```bash
ansible-playbook -i inventory/hosts.ini wordpress-ansible/rollback.yml
```

You must type `YES` to proceed.

---

## A Note on the Blog Post

One of the roles creates an actual blog post. It's written by the project's author (Sameer Malik) and appears under the title "About Me: My Journey into Technology and Web Development." It's an interesting artifact: the playbook that automates the website also writes the website's first real content.

You can delete it by re-running the playbook with `--skip-tags wordpress` and modifying the posts, or by accessing the WordPress admin dashboard directly.

---

## Security Highlights

- **SFTP chroot** — SFTP users can see only their own site folder, nothing else on the server
- **PHP-FPM per-user pools** — each site runs as its own Unix user; a compromised site can't access another's
- **SELinux** — booleans and file contexts restrict web processes to their expected directories
- **Firewall** — only HTTP, HTTPS, and (optionally) phpMyAdmin's port are open
- **Hardened `wp-config.php`** — `DISALLOW_FILE_EDIT` is `true`; the admin can't edit themes/plugins from the browser
- **phpMyAdmin** — behind Nginx Basic Auth *and* behind its own auth prompt; direct access to `/libraries` and `/templates` is blocked
- **SSL auto-renewal** — Certbot renews certificates daily at 03:00 without intervention

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Playbook fails on first task | Key permissions or security group | `chmod 400 your-key.pem` and check AWS SG for port 22 |
| "MODULE FAILURE" on MySQL tasks | Galaxy collections missing | `ansible-galaxy collection install -r requirements.yml` |
| Certbot fails | DNS not pointing to EC2 IP | `dig +short yourdomain.com` must match the server's IP |
| 502 Bad Gateway | PHP-FPM not listening | Check if `/var/run/php-fpm/bloguser.sock` exists |
| Can't access phpMyAdmin | Security group doesn't allow 8080 | Add 8080 rule to your EC2 SG (restrict to your IP) |
| WordPress "Error establishing database connection" | DB credentials mismatch | Compare `all.yml` with what the `mariadb` role created |
| Files not appearing in SFTP | SELinux denied writes | Check `/var/log/audit/audit.log` for AVC denials |

---

*Project by Sameer Malik | RHEL 10 on AWS | MariaDB 10.6 · PHP 8.3 · Nginx · Let's Encrypt · WordPress*
