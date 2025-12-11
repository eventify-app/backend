FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD sh -c "python manage.py migrate --noinput && \
            python manage.py collectstatic --noinput && \
            if [ \"$$SEED_ADMIN_ON_START\" = \"1\"]; then python manage.py seed_admin || true; else echo 'Skip seed_admin'; fi && \
            gunicorn eventify.wsgi:application -w 3 -k gthread -b 0.0.0.0:${PORT}"