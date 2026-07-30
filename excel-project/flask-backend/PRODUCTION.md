# Production Deployment

This deployment runs the Flask app behind Gunicorn with PostgreSQL and keeps it bound to localhost for an HTTPS reverse proxy.

## 1. Server prerequisites

Install Docker Engine, the Docker Compose plugin, Nginx, and Certbot on a Linux server. Point the chosen application domain (for example `school.example.com`) to the server.

## 2. Create production secrets

```bash
cd excel-project/flask-backend
cp .env.production.example .env.production
python -c "import secrets; print(secrets.token_urlsafe(64))"  # SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"  # ADMIN_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(32))"  # POSTGRES_PASSWORD
chmod 600 .env.production
```

Put the first generated value in `SECRET_KEY` and use generated values for `ADMIN_PASSWORD` and `POSTGRES_PASSWORD`. Repeat the database password in the password segment of `DATABASE_URL`; URL-encode it if it contains URL-reserved characters. Set `SYNC_API_KEY` to exactly the key shown in WordPress **Excel Schools → Sync Settings**. Never commit `.env.production`.

## 3. Start the application

```bash
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
docker compose --env-file .env.production -f compose.production.yml ps
curl http://127.0.0.1:8000/healthz
```

The entrypoint waits for PostgreSQL and initializes/upgrades the schema before Gunicorn starts. Uploaded files and PostgreSQL data live in named Docker volumes.

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

# Database backup
docker compose --env-file .env.production -f compose.production.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "backup-$(date +%F-%H%M).sql.gz"

# Uploaded-file backup
docker run --rm -v flask-backend_uploads:/data -v "$PWD":/backup alpine \
  tar czf /backup/uploads-$(date +%F-%H%M).tar.gz -C /data .
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
