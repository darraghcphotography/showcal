FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Everything except what .dockerignore excludes (aims.db, .env, uploads/,
# tests/, etc.) - used to be an explicit per-file COPY list, which silently
# left out every new top-level script/file until someone remembered to add
# it here too. Bit twice in one evening (CHANGELOG.md and export_awards.py
# both missing from an otherwise-successful deploy, purely because of this
# gap) before switching to a real .dockerignore instead.
COPY . .

# aims.db and uploaded posters live under /data, outside the image, so
# container upgrades never touch your actual data - see docker-compose.yml's
# volume mount.
ENV AIMS_DB_PATH=/data/aims.db
ENV AIMS_UPLOAD_DIR=/data/uploads
VOLUME /data

EXPOSE 8000
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8000", "wsgi:app"]
