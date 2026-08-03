FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY schema.sql wsgi.py import_csv.py export_csv.py import_awards.py seed_admin.py fix_show_titles.py backup_db.py enrich_show_info.py suggest_historical_regions.py ./
COPY ["AIMS_Awards - Results.csv", "./"]

# aims.db and uploaded posters live under /data, outside the image, so
# container upgrades never touch your actual data - see docker-compose.yml's
# volume mount.
ENV AIMS_DB_PATH=/data/aims.db
ENV AIMS_UPLOAD_DIR=/data/uploads
VOLUME /data

EXPOSE 8000
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8000", "wsgi:app"]
