# Hi 👋🏼 I'm Sameer Malik — Assignment Portfolio

---

## Who I Am

Hey, I'm Sameer — a tech enthusiast working on web development and cloud stuff. This folder is my collection of hands-on assignments from my learning journey. I didn't just read about these things — I built, tested, and documented each one so someone else could follow my steps.

---

## How I Approached These

For every assignment, I went through a cycle:

1. **Understand what the task was asking for** — whether it was "host a website," "automate a deploy," or "monitor server health."
2. **Plan the architecture** — which services I'd use (EC2, Nginx, MariaDB, Ansible) and how they'd connect.
3. **Build it** — write the actual configuration, run it, fix what broke, and get it working.
4. **Document the steps** — so the work could be repeated or reproduced by someone else.

For the bigger projects, I also tried to make them:

- **Modular** — broken into pieces (Ansible roles) so each one could be understood and reused independently.
- **Automated** — no manual clicks. If I could script it, I did.
- **Self-checking** — verification playbooks, monitoring dashboards, rollback scripts — I built ways to confirm things were right, and ways to undo them if wrong.

---

## What's Inside

### 🔧 Ansible WordPress Workflow

A complete playbook that provisions a WordPress server from scratch on AWS EC2 (RHEL 10). Nothing left to do by hand.

**8 Ansible roles:**

| # | Role | Does |
|---|------|------|
| 01 | `common` | System setup — hostname, timezone, swap, SELinux, firewall rules, repos (EPEL, Remi) |
| 02 | `mariadb` | MariaDB 10.6 install + secure config + database and user creation |
| 03 | `php` | PHP 8.3 with all WordPress extensions + dedicated PHP-FPM pool per user |
| 04 | `nginx` | Nginx + server blocks (WordPress + phpMyAdmin) |
| 05 | `user_sftp` | Linux user creation + SFTP chroot jail (restricted file transfer) |
| 06 | `wordpress` | Download WP + WP-CLI install + auto-create blog post + setup plugins |
| 07 | `phpmyadmin` | Latest PMA download + basic auth + Nginx config |
| 08 | `ssl` | Let's Encrypt certificate via Certbot + auto-renewal cron job |

**Extra files:** `verify.yml` (post-deploy checks), `rollback.yml` (complete undo).

I also wrote a full AWS guide (RHEL 10 manual setup) so you can see the same stack without Ansible.

---

### 📊 System Health Monitoring ("SysWatch")

A custom monitoring dashboard with two pieces:

- **`metrics_api.py`** — a local Flask API that pulls real system metrics (CPU, RAM, disk, I/O speed, per-process stats) from `psutil`. It binds to 127.0.0.1 only, requires an API key, and runs as a systemd service with security restrictions (`NoNewPrivileges`, `ProtectSystem=strict`).

- **`server-monitor-live.html`** — a dark-themed dashboard with live charts (Chart.js), showing system stats, per-process monitoring, and recent log entries. Refreshes automatically every few seconds.

- **`server-monitor.html`** — a static version of the dashboard for documentation/archival.

---

### 📝 Task #48777–#48804 (AWS & Server Assignments)

A series of solved AWS and server tasks, including:

| Task | What It Was |
|------|-------------|
| 48777 | **Main project** — Full WordPress stack (MariaDB + PHP 8 + Nginx + SSL + SFTP) |
| 48781 | Disk sharing with EBS (multi-attach) and EFS |
| 48784 | Disk-usage alerts via SNS |
| 48785 | Docker basics + container builds |
| 48786 | Server monitoring (Nagios, Zabbix) |
| 48787 | AWS Elastic Beanstalk configs |
| 48788 | Lambda + CloudWatch scheduled EC2 start/stop |
| 48789 | Email via PHP + AWS SES |
| 48790 | Git/GitHub setup |
| 48791 | IAM users with restricted permissions |
| 48792 | Load Balancer + Auto Scaling with PHP app |
| 48793 | Backup scripting + S3 sync |
| 48794 | Web hosting + DNS session (IPS R) |
| 48795 | Static website on AWS S3 |
| 48796 | Linux security — CSF, APF firewalls, security groups |
| 48797 | Website hosting errors (3xx–5xx) |
| 48798 | FTP/SFTP configuration |
| 48799 | NAT Gateway (public/private subnet architecture) |
| 48800 | WordPress on AWS RDS |
| 48801 | Virtual hosting in user directories |
| 48803 | Introduction to web hosting (Apache virtual hosts) |
| 48804 | Linux boot process, ports, admin commands |

Plus several session notes (cPanel/WHM, Nginx) and a DNS case study.

---

## Skills I've Built Along the Way

### Cloud & AWS
- EC2 (t2.micro RHEL 10), S3 (static hosting), RDS (managed DBs)
- EBS (multi-attach) and EFS (file sharing)
- Route53/DNS (A records, propagation)
- IAM users + policies (least-privilege access)
- Lambda scheduled functions + CloudWatch cron
- ELB (Application Load Balancer) + Auto Scaling
- Elastic Beanstalk environments

### DevOps & Automation
- **Ansible** — 8 roles, 8 tasks per role, handlers, Jinja2 templates, inventory management, tag-based partial runs, rollback playbooks
- **Docker** — container builds and commands
- **Jenkins** — CI/CD pipelines
- **Git** — remote repos, cloning, branching

### Web & Databases
- **Nginx** — server blocks, PHP-FPM socket, security headers
- **Apache** — virtual hosts, modules, default config
- **MariaDB 10.6** — secure install, users, databases, utf8mb4 collation
- **PHP 8.3** — extensions (mysqlnd, gd, curl, zip, mbstring, opcache…)
- **WordPress** — full stack, WP-CLI, plugins (Yoast, Wordfence, WP Super Cache)
- **phpMyAdmin** — latest version auto-detect, config generation, basic auth

### Linux Systems
- Boot process (grub → kernel → init → services)
- SFTP chroot jails (restricted file transfer)
- SELinux booleans + file contexts
- Firewalld rules
- System logging (journald, /var/log)
- System monitoring tools (Nagios, Zabbix)
- Server tuning (PageSpeed, Gzip, tuned)

### Scripting
- **Ansible** — the main scripting tool in this portfolio
- **Python** — Flask API, psutil metrics collection, background threads, threading locks
- **Bash** — backup scripts, S3 sync, automation

### Infrastructure as Code
- Role-based modular deployments (Ansible)
- Playbook-driven reproducible environments
- Configuration-as-code — every state can be reconstructed

---

## Quick Navigation

| Folder | What's There |
|--------|-------------|
| `ansible based workflow/wordpress-ansible/` | Full automated WordPress deploy (26 YAML files) |
| `System health monitoring/` | Flask API + HTML dashboards (3 files) |
| `AWS_WordPress_RHEL10_Setup_Guide.md` | Manual AWS setup walkthrough |
| `Task #48781 – 48804` | Individual task PDFs |

---

Happy to walk through any assignment or answer questions about how things work.
