# AWS WordPress Deployment Guide
### Red Hat Enterprise Linux 10 | t2.micro | MariaDB 10.6 | PHP 8.x | Nginx | SSL

---

> **⚠️ IMPORTANT NOTE:** "MONGO 10.6" in the task description is interpreted as **MariaDB 10.6**, since WordPress and phpMyAdmin both require a MySQL-compatible database. MongoDB is incompatible with WordPress and phpMyAdmin.

---

## PRE-REQUISITES BEFORE STARTING

- An AWS account with EC2 access
- A registered domain name (required for free SSL via Let's Encrypt)
- Domain's DNS A record pointing to your EC2 instance's public IP
- An SSH client (Terminal on Mac/Linux, or PuTTY/Windows Terminal on Windows)
- Your EC2 key pair `.pem` file downloaded

---

## PART 1 — LAUNCH THE EC2 INSTANCE ON AWS

### Step 1.1 — Launch Instance

1. Log in to **AWS Management Console** → go to **EC2 Dashboard**
2. Click **"Launch Instance"**
3. Fill in the following:
   - **Name:** `wordpress-server`
   - **AMI (Amazon Machine Image):** Search for **"Red Hat Enterprise Linux 10"** → Select the official RHEL 10 AMI (64-bit x86)
   - **Instance Type:** Select **`t2.micro`** (Free Tier eligible)
   - **Key Pair:** Select an existing key pair OR create a new one → Download the `.pem` file and save it securely
4. Under **Network Settings → Security Group**, click **"Edit"** and add the following **Inbound Rules:**

| Type        | Protocol | Port Range | Source      | Purpose               |
|-------------|----------|------------|-------------|-----------------------|
| SSH         | TCP      | 22         | My IP       | SSH access            |
| HTTP        | TCP      | 80         | 0.0.0.0/0   | Web traffic           |
| HTTPS       | TCP      | 443        | 0.0.0.0/0   | Secure web traffic    |
| Custom TCP  | TCP      | 8080       | My IP       | phpMyAdmin access     |

5. **Storage:** Keep default 10 GB gp3 (or increase to 20 GB for comfort)
6. Click **"Launch Instance"**

### Step 1.2 — Connect to the Instance via SSH

```bash
# On your local machine (Mac/Linux terminal):
chmod 400 /path/to/your-key.pem

ssh -i /path/to/your-key.pem ec2-user@YOUR_EC2_PUBLIC_IP
```

> On RHEL 10, the default user is **`ec2-user`** (not `ubuntu` or `root`)

### Step 1.3 — Point Your Domain to the Instance

In your domain registrar's DNS panel, add/update:
```
Type: A
Name: @ (or your subdomain, e.g., www)
Value: YOUR_EC2_PUBLIC_IP
TTL: 300
```
Also add:
```
Type: A
Name: www
Value: YOUR_EC2_PUBLIC_IP
TTL: 300
```
> DNS propagation may take 5–30 minutes. Continue with server setup while it propagates.

---

## PART 2 — INITIAL SERVER SETUP

### Step 2.1 — Switch to Root and Update System

```bash
sudo -i
```

```bash
# Update all packages
dnf update -y
```

### Step 2.2 — Set Hostname

```bash
hostnamectl set-hostname wordpress-server
```

### Step 2.3 — Set Timezone

```bash
timedatectl set-timezone Asia/Kolkata
# Verify
timedatectl
```

### Step 2.4 — Add Swap Space (Important for t2.micro with 1 GB RAM)

```bash
# Create a 2 GB swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Make swap permanent across reboots
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Verify swap is active
free -h
```

---

## PART 3 — INSTALL REQUIRED PACKAGES

### Step 3.1 — Install EPEL Repository

```bash
dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-10.noarch.rpm
dnf config-manager --enable epel
```

### Step 3.2 — Install Remi Repository (for PHP 8.x)

```bash
dnf install -y https://rpms.remirepo.net/enterprise/remi-release-10.rpm
```

> If RHEL 10 Remi package is not yet available, use the RHEL 9 compatible version:
> `dnf install -y https://rpms.remirepo.net/enterprise/remi-release-9.rpm`

### Step 3.3 — Enable PHP 8.3 from Remi

```bash
# List available PHP streams
dnf module list php

# Enable PHP 8.3 from Remi repository
dnf module enable php:remi-8.3 -y
```

### Step 3.4 — Install PHP 8.3 and Required Extensions

```bash
dnf install -y \
  php \
  php-fpm \
  php-mysqlnd \
  php-xml \
  php-json \
  php-mbstring \
  php-curl \
  php-zip \
  php-gd \
  php-intl \
  php-opcache \
  php-imagick \
  php-sodium \
  php-bcmath
```

```bash
# Verify PHP version (must be 8.x or higher)
php -v
```

Expected output:
```
PHP 8.3.x (cli) (built: ...) ...
```

### Step 3.5 — Install Nginx

```bash
dnf install -y nginx
```

```bash
# Start and enable Nginx
systemctl start nginx
systemctl enable nginx

# Verify status
systemctl status nginx
```

### Step 3.6 — Configure MariaDB 10.6 Repository

```bash
# Create MariaDB repo file
cat > /etc/yum.repos.d/mariadb.repo << 'EOF'
[mariadb]
name = MariaDB
baseurl = https://downloads.mariadb.com/MariaDB/mariadb-10.6/yum/rhel/9/x86_64
gpgkey = https://downloads.mariadb.com/MariaDB/MariaDB-Server-GPG-KEY
gpgcheck = 1
enabled = 1
EOF
```

> Note: Use the RHEL 9 repo for RHEL 10 compatibility until official RHEL 10 repos are available.

### Step 3.7 — Install MariaDB 10.6

```bash
dnf install -y MariaDB-server MariaDB-client
```

```bash
# Start and enable MariaDB
systemctl start mariadb
systemctl enable mariadb

# Verify version
mysql --version
```

Expected output:
```
mysql  Ver 15.1 Distrib 10.6.x-MariaDB ...
```

### Step 3.8 — Secure MariaDB Installation

```bash
mysql_secure_installation
```

Answer the prompts as follows:
```
Enter current password for root (enter for none): [PRESS ENTER]
Switch to unix_socket authentication [Y/n]: n
Change the root password? [Y/n]: Y
New password: CHANGE_ME
Re-enter new password: CHANGE_ME
Remove anonymous users? [Y/n]: Y
Disallow root login remotely? [Y/n]: Y
Remove test database and access to it? [Y/n]: Y
Reload privilege tables now? [Y/n]: Y
```

---

## PART 4 — CREATE USER AND DIRECTORY STRUCTURE

### Step 4.1 — Define Variables (Use Your Own Values)

```bash
# Set your variables (replace with actual values)
USERNAME="bloguser"
SITENAME="myblog"
USER_PASSWORD="CHANGE_ME"
DOMAIN="yourdomain.com"
```

### Step 4.2 — Create the System User

```bash
# Create user with home directory under /home
useradd -m -d /home/$USERNAME -s /bin/bash $USERNAME

# Set a strong password for the user
echo "$USERNAME:$USER_PASSWORD" | chpasswd

# Verify user was created
id $USERNAME
```

### Step 4.3 — Create the Website Directory Structure

```bash
# Create the full path as specified: /home/username/websitename/public
mkdir -p /home/$USERNAME/$SITENAME/public

# Create supporting directories
mkdir -p /home/$USERNAME/$SITENAME/logs
mkdir -p /home/$USERNAME/$SITENAME/tmp

# Set ownership — user owns their directory, nginx needs read access
chown -R $USERNAME:$USERNAME /home/$USERNAME/
chmod 755 /home/$USERNAME/
chmod 755 /home/$USERNAME/$SITENAME/
chmod 755 /home/$USERNAME/$SITENAME/public/

# Verify directory structure
ls -la /home/$USERNAME/$SITENAME/
```

Expected output:
```
drwxr-xr-x. logs/
drwxr-xr-x. public/
drwxr-xr-x. tmp/
```

### Step 4.4 — Add nginx User to the Website User's Group

```bash
# Add nginx to the user's group so it can read website files
usermod -aG $USERNAME nginx

# Verify
groups nginx
```

---

## PART 5 — CONFIGURE SFTP ACCESS

SFTP uses OpenSSH (already installed on RHEL). We'll configure a dedicated SFTP-only group with chroot jail for security.

### Step 5.1 — Create SFTP Group

```bash
groupadd sftpusers
usermod -aG sftpusers $USERNAME
```

### Step 5.2 — Configure SSH/SFTP in sshd_config

```bash
# Open the SSH configuration file
nano /etc/ssh/sshd_config
```

Scroll to the **bottom** of the file and add the following block:

```
# ====== SFTP Configuration ======
# Comment out or override the default Subsystem line if it exists:
# Subsystem sftp /usr/lib/openssh/sftp-server

# Add our chrooted SFTP configuration
Match Group sftpusers
    ChrootDirectory /home/%u
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
    PasswordAuthentication yes
```

Also ensure this line exists (and is NOT commented out) near the top:
```
Subsystem sftp internal-sftp
```

> **Important:** If you see `Subsystem sftp /usr/libexec/openssh/sftp-server`, comment it out and replace with `Subsystem sftp internal-sftp`

Save the file: `CTRL+X` → `Y` → `ENTER`

### Step 5.3 — Fix ChrootDirectory Permissions

For SFTP chroot to work, the chroot directory must be owned by root:

```bash
# The chroot directory (/home/username) must be owned by ROOT
chown root:root /home/$USERNAME
chmod 755 /home/$USERNAME

# The website subfolder is owned by the user
chown -R $USERNAME:$USERNAME /home/$USERNAME/$SITENAME/
```

### Step 5.4 — Allow Password Authentication for SFTP

```bash
# In /etc/ssh/sshd_config, ensure:
grep "PasswordAuthentication" /etc/ssh/sshd_config
```

If it shows `PasswordAuthentication no`, change it to `yes`:
```bash
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
```

### Step 5.5 — Restart SSH Service

```bash
# Test configuration first
sshd -t

# If no errors, restart
systemctl restart sshd
systemctl status sshd
```

### Step 5.6 — Test SFTP Connection

From your **local machine**, open a new terminal:

```bash
sftp -P 22 bloguser@YOUR_EC2_PUBLIC_IP
```

Enter the password when prompted. You should see:
```
Connected to YOUR_EC2_PUBLIC_IP.
sftp> ls
myblog
sftp> cd myblog/public
sftp> pwd
Remote working directory: /myblog/public
sftp> exit
```

> **SFTP Credentials:**
> - Host: `YOUR_EC2_PUBLIC_IP`
> - Username: `bloguser`
> - Password: `CHANGE_ME`
> - Port: `22`
> - Protocol: `SFTP`

You can also use GUI clients like **FileZilla** or **WinSCP** with these credentials.

---

## PART 6 — CONFIGURE PHP-FPM

### Step 6.1 — Create a PHP-FPM Pool for the User

```bash
# Create a dedicated PHP-FPM pool config for the website user
cat > /etc/php-fpm.d/$USERNAME.conf << EOF
[$USERNAME]
user = $USERNAME
group = $USERNAME
listen = /var/run/php-fpm/$USERNAME.sock
listen.owner = nginx
listen.group = nginx
listen.mode = 0660
pm = dynamic
pm.max_children = 5
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 3
pm.max_requests = 500
php_admin_value[error_log] = /home/$USERNAME/$SITENAME/logs/php-error.log
php_admin_flag[log_errors] = on
php_value[session.save_handler] = files
php_value[session.save_path] = /home/$USERNAME/$SITENAME/tmp/
php_value[upload_max_filesize] = 64M
php_value[post_max_size] = 64M
php_value[memory_limit] = 256M
php_value[max_execution_time] = 300
EOF
```

### Step 6.2 — Remove or Disable the Default PHP-FPM Pool

```bash
# Disable the default www pool to avoid conflicts
mv /etc/php-fpm.d/www.conf /etc/php-fpm.d/www.conf.disabled
```

### Step 6.3 — Start and Enable PHP-FPM

```bash
systemctl start php-fpm
systemctl enable php-fpm
systemctl status php-fpm
```

---

## PART 7 — CREATE THE DATABASE FOR WORDPRESS

### Step 7.1 — Create WordPress Database and User

```bash
mysql -u root -p
```
Enter your root password (`CHANGE_ME`), then run these SQL commands:

```sql
-- Create the database
CREATE DATABASE myblog_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create a dedicated database user
CREATE USER 'myblog_user'@'localhost' IDENTIFIED BY 'CHANGE_ME';

-- Grant privileges
GRANT ALL PRIVILEGES ON myblog_db.* TO 'myblog_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Verify
SHOW DATABASES;
SELECT user, host FROM mysql.user;

-- Exit MariaDB
EXIT;
```

---

## PART 8 — INSTALL WORDPRESS

### Step 8.1 — Download WordPress

```bash
cd /tmp
wget https://wordpress.org/latest.tar.gz
tar -xzf latest.tar.gz
```

### Step 8.2 — Move WordPress to the Site Root

```bash
# Copy WordPress files to the public directory
cp -r /tmp/wordpress/* /home/$USERNAME/$SITENAME/public/

# Set correct ownership
chown -R $USERNAME:$USERNAME /home/$USERNAME/$SITENAME/public/
chmod -R 755 /home/$USERNAME/$SITENAME/public/
chmod -R 644 /home/$USERNAME/$SITENAME/public/*.php
chmod 755 /home/$USERNAME/$SITENAME/public/wp-content/
```

### Step 8.3 — Create WordPress Configuration File

```bash
cd /home/$USERNAME/$SITENAME/public/

# Copy sample config
cp wp-config-sample.php wp-config.php

# Edit the config file
nano wp-config.php
```

Find and replace the following lines (use CTRL+W to search in nano):

```php
/** The name of the database for WordPress */
define( 'DB_NAME', 'myblog_db' );

/** Database username */
define( 'DB_USER', 'myblog_user' );

/** Database password */
define( 'DB_PASSWORD', 'CHANGE_ME' );

/** Database host */
define( 'DB_HOST', 'localhost' );

/** Database charset */
define( 'DB_CHARSET', 'utf8mb4' );
```

Also update the **security keys** — visit https://api.wordpress.org/secret-key/1.1/salt/ and replace the placeholder keys section with the generated values.

Save and exit: `CTRL+X` → `Y` → `ENTER`

```bash
# Fix ownership after editing
chown $USERNAME:$USERNAME /home/$USERNAME/$SITENAME/public/wp-config.php
chmod 640 /home/$USERNAME/$SITENAME/public/wp-config.php
```

---

## PART 9 — CONFIGURE NGINX

### Step 9.1 — Create Nginx Server Block for the Website

```bash
cat > /etc/nginx/conf.d/$SITENAME.conf << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;

    root /home/$USERNAME/$SITENAME/public;
    index index.php index.html index.htm;

    access_log /home/$USERNAME/$SITENAME/logs/access.log;
    error_log  /home/$USERNAME/$SITENAME/logs/error.log;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;

    client_max_body_size 64M;

    location / {
        try_files \$uri \$uri/ /index.php?\$args;
    }

    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php-fpm/$USERNAME.sock;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
        include fastcgi_params;
        fastcgi_read_timeout 300;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires max;
        log_not_found off;
    }

    location = /favicon.ico {
        log_not_found off;
        access_log off;
    }

    location = /robots.txt {
        allow all;
        log_not_found off;
        access_log off;
    }

    # Block access to sensitive files
    location ~* /\.(ht|git|svn) {
        deny all;
    }

    location ~ /wp-config\.php {
        deny all;
    }
}
EOF
```

### Step 9.2 — Test and Reload Nginx

```bash
# Test configuration
nginx -t

# If output says "syntax is ok" and "test is successful":
systemctl reload nginx
```

### Step 9.3 — Fix SELinux Policies (RHEL-specific)

RHEL 10 has SELinux enabled by default. You must configure it to allow Nginx to access the user's home directory:

```bash
# Allow Nginx to read from /home directories
setsebool -P httpd_read_user_content 1

# Allow Nginx to connect to PHP-FPM socket
setsebool -P httpd_execmem 1

# Allow PHP-FPM to write to the website directory
chcon -R -t httpd_sys_rw_content_t /home/$USERNAME/$SITENAME/public/wp-content/
chcon -R -t httpd_sys_rw_content_t /home/$USERNAME/$SITENAME/tmp/
chcon -R -t httpd_sys_rw_content_t /home/$USERNAME/$SITENAME/logs/

# Allow Nginx to access home directories
setsebool -P httpd_enable_homedirs 1

# Verify SELinux context
ls -Z /home/$USERNAME/$SITENAME/public/
```

### Step 9.4 — Configure Firewall

```bash
# Check if firewalld is running
systemctl status firewalld

# If running, allow HTTP and HTTPS traffic
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --permanent --add-port=8080/tcp
firewall-cmd --reload

# Verify
firewall-cmd --list-all
```

---

## PART 10 — INSTALL FREE SSL CERTIFICATE (Let's Encrypt)

> **Prerequisite:** Your domain's DNS must already be pointing to this server's IP before running Certbot.

### Step 10.1 — Install Certbot

```bash
dnf install -y certbot python3-certbot-nginx
```

### Step 10.2 — Obtain SSL Certificate

```bash
certbot --nginx -d $DOMAIN -d www.$DOMAIN \
  --non-interactive \
  --agree-tos \
  --email admin@$DOMAIN \
  --redirect
```

Certbot will:
- Verify domain ownership via HTTP challenge
- Download the free Let's Encrypt certificate
- Automatically modify your Nginx config to enable HTTPS
- Set up HTTP → HTTPS redirect

### Step 10.3 — Verify HTTPS is Working

```bash
# Check certificate details
certbot certificates

# Verify Nginx config was updated correctly
cat /etc/nginx/conf.d/$SITENAME.conf

# Test Nginx config
nginx -t
systemctl reload nginx
```

Visit `https://yourdomain.com` in your browser — you should see a padlock icon.

### Step 10.4 — Set Up Auto-Renewal

Let's Encrypt certificates expire every 90 days. Set up auto-renewal:

```bash
# Test renewal (dry run — doesn't actually renew)
certbot renew --dry-run

# Add renewal cron job
echo "0 3 * * * root certbot renew --quiet --post-hook 'systemctl reload nginx'" >> /etc/crontab

# Verify crontab entry
tail -3 /etc/crontab
```

---

## PART 11 — CONFIGURE phpMyAdmin

### Step 11.1 — Download phpMyAdmin

```bash
cd /tmp
# Get the latest phpMyAdmin version
wget https://www.phpmyadmin.net/downloads/phpMyAdmin-latest-all-languages.tar.gz
tar -xzf phpMyAdmin-latest-all-languages.tar.gz
```

### Step 11.2 — Install phpMyAdmin to a Secure Location

```bash
# Create phpMyAdmin directory
mkdir -p /usr/share/phpmyadmin

# Move files
mv /tmp/phpMyAdmin-*-all-languages/* /usr/share/phpmyadmin/

# Copy and configure
cp /usr/share/phpmyadmin/config.sample.inc.php /usr/share/phpmyadmin/config.inc.php

# Generate a blowfish secret (32 random characters)
BLOWFISH=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
echo "Your blowfish secret: $BLOWFISH"
```

### Step 11.3 — Configure phpMyAdmin

```bash
nano /usr/share/phpmyadmin/config.inc.php
```

Find and update:
```php
/* Authentication type */
$cfg['blowfish_secret'] = 'YOUR_32_CHAR_RANDOM_STRING_HERE'; /* YOU MUST FILL IN THIS FOR COOKIE AUTH! */

/* Server parameters */
$cfg['Servers'][$i]['host'] = 'localhost';
$cfg['Servers'][$i]['auth_type'] = 'cookie';
$cfg['Servers'][$i]['AllowNoPassword'] = false;

/* Optional: Restrict access to specific database user */
$cfg['Servers'][$i]['only_db'] = '';  // Leave empty for all databases
```

Replace `YOUR_32_CHAR_RANDOM_STRING_HERE` with the output of the `$BLOWFISH` variable above.

Save and exit.

### Step 11.4 — Create phpMyAdmin Temp Directory

```bash
mkdir -p /usr/share/phpmyadmin/tmp
chmod 777 /usr/share/phpmyadmin/tmp
chown -R nginx:nginx /usr/share/phpmyadmin/
```

### Step 11.5 — Create phpMyAdmin Nginx Configuration

We'll serve phpMyAdmin on port 8080 (restricted to your IP via security group):

```bash
cat > /etc/nginx/conf.d/phpmyadmin.conf << EOF
server {
    listen 8080;
    server_name $DOMAIN YOUR_EC2_PUBLIC_IP;

    root /usr/share/phpmyadmin;
    index index.php index.html;

    access_log /var/log/nginx/phpmyadmin_access.log;
    error_log  /var/log/nginx/phpmyadmin_error.log;

    # Basic authentication for extra security
    auth_basic "phpMyAdmin - Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        try_files \$uri \$uri/ /index.php?\$args;
    }

    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php-fpm/$USERNAME.sock;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
        include fastcgi_params;
    }

    # Block access to sensitive phpMyAdmin directories
    location ~* ^/phpmyadmin/(libraries|templates|setup/lib) {
        deny all;
        return 403;
    }
}
EOF
```

### Step 11.6 — Create HTTP Basic Auth for phpMyAdmin (Extra Layer of Security)

```bash
# Install httpd-tools for htpasswd
dnf install -y httpd-tools

# Create the password file (replace 'adminuser' and prompt will ask for password)
htpasswd -c /etc/nginx/.htpasswd pmaadmin
# Enter and confirm a password when prompted, e.g.: CHANGE_ME
```

### Step 11.7 — Set SELinux Context for phpMyAdmin

```bash
chcon -R -t httpd_sys_content_t /usr/share/phpmyadmin/
chcon -R -t httpd_sys_rw_content_t /usr/share/phpmyadmin/tmp/
```

### Step 11.8 — Test and Reload Nginx

```bash
nginx -t
systemctl reload nginx
```

### Step 11.9 — Access phpMyAdmin

Open a browser and go to:
```
http://YOUR_EC2_PUBLIC_IP:8080
```
or
```
http://yourdomain.com:8080
```

**Login credentials:**
- Basic Auth prompt: Username `pmaadmin`, Password `CHANGE_ME`
- phpMyAdmin login: Username `myblog_user`, Password `CHANGE_ME`
- (Or use `root` with your MariaDB root password for full access)

> **phpMyAdmin Credentials:**
> - URL: `http://yourdomain.com:8080`
> - Basic Auth Username: `pmaadmin`
> - Basic Auth Password: `CHANGE_ME`
> - DB Username: `myblog_user`
> - DB Password: `CHANGE_ME`

---

## PART 12 — COMPLETE WORDPRESS INSTALLATION

### Step 12.1 — Verify All Services Are Running

```bash
systemctl status nginx
systemctl status php-fpm
systemctl status mariadb
```

All three should show `active (running)`.

### Step 12.2 — Run the WordPress Web Installer

1. Open your browser and visit: `https://yourdomain.com`
2. You'll see the **WordPress Installation Page**
3. Select your **language** → Click **"Continue"**
4. Fill in the **Site Information:**

   | Field | Value |
   |-------|-------|
   | Site Title | My Personal Blog |
   | Username | `wpadmin` |
   | Password | `CHANGE_ME` |
   | Your Email | `your@email.com` |
   | Search Engine Visibility | ✅ Allow search engines to index this site |

5. Click **"Install WordPress"**
6. You'll see **"Success!"** — Click **"Log In"**

### Step 12.3 — Log In to WordPress Dashboard

- URL: `https://yourdomain.com/wp-admin`
- Username: `wpadmin`
- Password: `CHANGE_ME`

> **WordPress Credentials:**
> - WordPress Admin URL: `https://yourdomain.com/wp-admin`
> - Username: `wpadmin`
- Password: `CHANGE_ME`

---

## PART 13 — WORDPRESS DASHBOARD CONFIGURATION

### Step 13.1 — Set Permalink Structure

1. In the WP Admin dashboard, go to **Settings → Permalinks**
2. Select **"Post name"** (`/%postname%/`)
3. Click **"Save Changes"**

This creates SEO-friendly URLs like `https://yourdomain.com/my-first-blog-post/`

### Step 13.2 — Update General Settings

Go to **Settings → General:**
- Site Title: `My Personal Blog`
- Tagline: `Thoughts, ideas, and stories`
- WordPress Address (URL): `https://yourdomain.com`
- Site Address (URL): `https://yourdomain.com`
- Administration Email Address: `your@email.com`
- Timezone: Set to your timezone (e.g., `Asia/Kolkata`)
- Date Format: Choose preferred format
- Click **"Save Changes"**

### Step 13.3 — Update Discussion Settings

Go to **Settings → Discussion:**
- ✅ Allow people to submit comments on new posts
- ✅ Comment author must fill out name and email
- ✅ Enable comment moderation
- Click **"Save Changes"**

### Step 13.4 — Set a Theme

1. Go to **Appearance → Themes**
2. The default **"Twenty Twenty-Four"** theme is already active — this is a modern, clean theme suitable for personal blogs
3. To customize: Go to **Appearance → Customize**
   - Upload a site logo (optional)
   - Set site icon/favicon (optional)
   - Choose a color palette
   - Set typography
4. Click **"Publish"** to save changes

### Step 13.5 — Delete Default Content

1. Go to **Posts → All Posts** → Delete the default **"Hello World!"** post (move to Trash → Empty Trash)
2. Go to **Pages → All Pages** → Delete the default **"Sample Page"**
3. Go to **Comments** → Delete the default "Mr. WordPress" comment

### Step 13.6 — Create Required Pages

Go to **Pages → Add New** and create the following pages:

**About Page:**
- Title: `About Me`
- Content: A brief bio about yourself
- Click **"Publish"**

**Contact Page:**
- Title: `Contact`
- Content: Your contact information or a contact form message
- Click **"Publish"**

### Step 13.7 — Set Up Navigation Menu

1. Go to **Appearance → Menus**
2. Create a new menu called **"Main Menu"**
3. Add pages: Home, About Me, Blog, Contact
4. Assign to location: **"Primary Menu"**
5. Click **"Save Menu"**

### Step 13.8 — Install Essential Plugins

Go to **Plugins → Add New** and install:

1. **Yoast SEO** — Search engine optimization
   - Search: "Yoast SEO" → Install → Activate
   
2. **Wordfence Security** — Website security
   - Search: "Wordfence" → Install → Activate
   
3. **WP Super Cache** — Page caching for performance
   - Search: "WP Super Cache" → Install → Activate
   - After activating, go to **Settings → WP Super Cache → Enable Caching → Update Status**

4. **UpdraftPlus** — Automatic backups
   - Search: "UpdraftPlus" → Install → Activate

---

## PART 14 — WRITE YOUR PERSONAL BLOG POST

### Step 14.1 — Create a New Blog Post

1. In the WP Admin, go to **Posts → Add New**
2. The WordPress Block Editor (Gutenberg) will open

### Step 14.2 — Write Your Post

**Title:** (click "Add title" at the top)
```
About Me: My Journey into Technology and Web Development
```

**Content** (add the following blocks):

Click the **"+"** button to add blocks. Start with a **Paragraph** block:

---

*Sample personal blog post content — customize with your own details:*

```
Hello and welcome to my personal blog! My name is [Your Name], and I'm 
thrilled to share my journey with you through this space.

[Add a heading block: "Who Am I?"]

I am a technology enthusiast and aspiring web developer based in [Your Location]. 
I have always been fascinated by how technology can transform the way we live, 
work, and connect with one another. This blog is my digital journal — a place 
where I will document my learning, share my experiences, and connect with 
like-minded individuals.

[Add a heading block: "My Background"]

My journey into tech began [describe your background]. I started exploring 
Linux and server administration, which eventually led me to set up this very 
website on an AWS cloud server running Red Hat Enterprise Linux — a milestone 
I am incredibly proud of!

[Add a heading block: "What You Can Expect Here"]

On this blog, you can look forward to:
- Tutorials and how-to guides on web development and server management
- Reflections on what I am currently learning
- Personal stories and experiences
- Tips and tricks I discover along the way

[Add a heading block: "Let's Connect"]

I believe that learning is best when it is shared. If you are on a similar 
journey or simply want to say hello, please feel free to reach out through 
the Contact page. I look forward to meeting you!

Thank you for visiting, and I hope you find something here that inspires or 
helps you.

Warm regards,
[Your Name]
```

### Step 14.3 — Add a Featured Image

1. In the right sidebar, find **"Featured image"**
2. Click **"Set featured image"**
3. Upload a professional photo of yourself or a relevant image
4. Click **"Set featured image"**

### Step 14.4 — Configure Post Settings

In the right sidebar:
- **Category:** Create a new category called "Personal" → Click "Add New Category"
- **Tags:** Add tags like `introduction`, `about me`, `web development`, `aws`
- **Excerpt:** Write a short 1–2 sentence description of the post

### Step 14.5 — Publish the Post

1. Click the **"Publish"** button (top right)
2. Click **"Publish"** again to confirm
3. Click **"View Post"** to see your live blog post

---

## PART 15 — FINAL VERIFICATION CHECKLIST

Run all of these checks to confirm everything is working:

```bash
# Check all services
systemctl status nginx php-fpm mariadb

# Check SSL certificate
certbot certificates

# Check disk usage
df -h

# Check memory usage
free -h

# Check PHP version
php -v

# Check MariaDB version
mysql --version

# Test Nginx config
nginx -t

# Check open ports
ss -tlnp | grep -E ':80|:443|:8080|:22'

# Check website directory
ls -la /home/bloguser/myblog/public/
```

### Browser Tests:
- [ ] `https://yourdomain.com` loads WordPress site with padlock
- [ ] `https://yourdomain.com/wp-admin` loads WordPress admin login
- [ ] `http://yourdomain.com:8080` loads phpMyAdmin (with basic auth prompt)
- [ ] SFTP connection works with FileZilla/WinSCP
- [ ] Blog post is visible at `https://yourdomain.com/about-me-my-journey/`

---

## PART 16 — CREDENTIALS SUMMARY

> ⚠️ **SECURITY REMINDER:** Change all passwords below to your own strong, unique passwords before deploying. Never share these credentials publicly.

---

### 🔐 SFTP Credentials
| Field | Value |
|-------|-------|
| Host | `YOUR_EC2_PUBLIC_IP` |
| Port | `22` |
| Protocol | `SFTP` |
| Username | `bloguser` |
| Password | `CHANGE_ME` |
| Root Path | `/myblog/public` |

---

### 🗄️ phpMyAdmin Credentials
| Field | Value |
|-------|-------|
| URL | `http://yourdomain.com:8080` |
| Basic Auth Username | `pmaadmin` |
| Basic Auth Password | `CHANGE_ME` |
| DB Username | `myblog_user` |
| DB Password | `CHANGE_ME` |
| DB Name | `myblog_db` |

---

### 🌐 WordPress Credentials
| Field | Value |
|-------|-------|
| WordPress Admin URL | `https://yourdomain.com/wp-admin` |
| Username | `wpadmin` |
| Password | `CHANGE_ME` |
| Email | `your@email.com` |

---

### 🔑 MariaDB Root (Server-side only)
| Field | Value |
|-------|-------|
| Username | `root` |
| MariaDB root password | `CHANGE_ME` |
| Access | Localhost only (via `mysql -u root -p`) |

---

## APPENDIX A — TROUBLESHOOTING

### Nginx 502 Bad Gateway
```bash
# Check PHP-FPM is running and socket exists
systemctl status php-fpm
ls -la /var/run/php-fpm/

# Check PHP-FPM error log
tail -50 /home/bloguser/myblog/logs/php-error.log
journalctl -u php-fpm --no-pager -n 50
```

### 403 Forbidden
```bash
# Check SELinux context
ls -Z /home/bloguser/myblog/public/
restorecon -Rv /home/bloguser/myblog/public/

# Check permissions
ls -la /home/bloguser/
chmod 755 /home/bloguser/
```

### SFTP Permission Denied
```bash
# Verify chroot ownership (must be root:root)
ls -ld /home/bloguser
chown root:root /home/bloguser
chmod 755 /home/bloguser
systemctl restart sshd
```

### SSL Certificate Fails
```bash
# Check DNS is resolving to your IP
nslookup yourdomain.com

# Try certbot with verbose output
certbot --nginx -d yourdomain.com --verbose
```

### Can't Write to WordPress wp-content
```bash
chown -R bloguser:bloguser /home/bloguser/myblog/public/wp-content/
chcon -R -t httpd_sys_rw_content_t /home/bloguser/myblog/public/wp-content/
```

---

## APPENDIX B — USEFUL SERVER COMMANDS

```bash
# Restart all web services
systemctl restart nginx php-fpm mariadb

# View real-time Nginx access logs
tail -f /home/bloguser/myblog/logs/access.log

# View real-time Nginx error logs
tail -f /home/bloguser/myblog/logs/error.log

# Monitor server resources
top
htop  # (install with: dnf install -y htop)

# Check website disk usage
du -sh /home/bloguser/myblog/

# Manually renew SSL
certbot renew

# Backup database
mysqldump -u myblog_user -p myblog_db > /home/bloguser/myblog_backup_$(date +%F).sql
```

---

*Guide version 1.0 | Red Hat Enterprise Linux 10 | MariaDB 10.6 | PHP 8.3 | Nginx | Let's Encrypt SSL | WordPress*
