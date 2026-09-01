FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# non-root user (files dir is for uploads; DB lives in the Postgres container)
RUN useradd -m appuser && mkdir -p /app/data/files && chown -R appuser /app/data
USER appuser
EXPOSE 8000
# LIBRARY_DATABASE_URL / LIBRARY_STORAGE_DIR are injected by docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
