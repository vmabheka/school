# Production Deployment

This deployment runs the Flask app behind Gunicorn with PostgreSQL and keeps it bound to localhost for an HTTPS reverse proxy.

## 1. Server prerequisites

Install Docker Engine, the Docker Compose plugin, Nginx, and Certbot on a Linux server. Point the chosen application domain (for example `school.example.com`) to the server.

## 2. Create production secrets

```bash
cd excel-project/flask-backend
python3 generate-production-env.py
nano .env.production
```

The generator creates secure `SECRET_KEY`, `ADMIN_PASSWORD`, and matching PostgreSQL/DATABASE_URL password values, then protects the file with mode `0600`. Set `SYNC_API_KEY` to exactly the key shown in WordPress **Excel Schools → Sync Settings** and review the public domain/origin values. Never commit `.env.production`.

## 3. Start the application

```bash
./deploy-production.sh
```

The deployment script validates the environment, renders the Compose configuration, builds the current application image, starts PostgreSQL and Gunicorn, waits for `/healthz`, and prints service status. The container entrypoint waits for PostgreSQL and initializes/upgrades the schema before Gunicorn starts. Uploaded files and PostgreSQL data live in named Docker volumes.

## 4. Configure HTTPS

```bash
sudo cp nginx-excel-schools.conf.example /etc/nginx/sites-available/excel-schools
sudo nano /etc/nginx/sites-available/excel-schools  # replace app.example.com
sudo ln -s /etc/nginx/sites-available/excel-schools /etc/nginx/sites-enabled/excel-schools
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d school.example.com
```

Keep `TRUST_PROXY=true`; this lets Flask recognize HTTPS forwarded by Nginx and issue secure session cookies.

## 5. Operations

```bash
# Logs
docker compose --env-file .env.production -f compose.production.yml logs -f web

# Deploy an update
git pull
docker compose --env-file .env.production -f compose.production.yml build web
docker compose --env-file .env.production -f compose.production.yml up -d web

# Database + upload backup, with SHA-256 checksums
./backup-production.sh

# Store backups elsewhere
BACKUP_DIR=/secure/off-server-mount ./backup-production.sh
```

Test restoring backups before launch and on a regular schedule. Restrict SSH, enable a firewall, keep only ports 22/80/443 public, and use an off-server backup destination.

## Launch checklist

- DNS points to the production server.
- HTTPS works and HTTP redirects to HTTPS after Certbot configuration.
- `/healthz` reports `status: ok`.
- A unique 32+ character `SECRET_KEY` is configured.
- PostgreSQL uses a strong password and is not publicly exposed.
- WordPress and Flask use the same sync API key and the REST endpoint ends in `/wp-json/excel-schools/v2`.
- Unique `ADMIN_USERNAME` and 16+ character `ADMIN_PASSWORD` values are configured before first start.
- Admin, bursar, and teacher permissions are tested with separate accounts.
- Manual JSON export/import and automatic sync are tested.
- Database and upload backups are tested.
