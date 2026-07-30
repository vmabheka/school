"""Gunicorn configuration shared by native and container deployments."""

import multiprocessing
import os

bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8000')
workers = int(os.environ.get('WEB_WORKERS', str(min(multiprocessing.cpu_count() * 2 + 1, 4))))
threads = int(os.environ.get('WEB_THREADS', '4'))
timeout = int(os.environ.get('WEB_TIMEOUT', '120'))
graceful_timeout = int(os.environ.get('WEB_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.environ.get('WEB_KEEPALIVE', '5'))
max_requests = int(os.environ.get('WEB_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.environ.get('WEB_MAX_REQUESTS_JITTER', '100'))
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
capture_output = True
worker_tmp_dir = '/dev/shm' if os.path.isdir('/dev/shm') else None
# Only trust forwarded headers from the local reverse proxy by default.
forwarded_allow_ips = os.environ.get('FORWARDED_ALLOW_IPS', '127.0.0.1')
