#!/bin/sh
cd /opt/flansible ;
/opt/flansible/venv/bin/python /opt/flansible/venv/bin/gunicorn -b 0.0.0.0:8000 -k gevent --worker-connections 1000 --timeout 900 run:app -D;
/opt/flansible/venv/bin/python /opt/flansible/venv/bin/gunicorn -b 0.0.0.0:8001 -k gevent --worker-connections 1000 --timeout 900 run:app -D;
/opt/flansible/venv/bin/python /opt/flansible/venv/bin/gunicorn -b 0.0.0.0:8002 -k gevent --worker-connections 1000 --timeout 900 run:app -D;
/opt/flansible/venv/bin/python /opt/flansible/venv/bin/gunicorn -b 0.0.0.0:8003 -k gevent --worker-connections 1000 --timeout 900 run:app -D;
/usr/bin/redis-server &
celery beat -A app.celery --loglevel=INFO --logfile=/opt/app/Zanother_celer/flansible/app/logs/server.log --detach;
celery worker -A app.celery --loglevel=INFO --logfile=/opt/app/Zanother_celer/flansible/app/logs/server.log --detach ;
