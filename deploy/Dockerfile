FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AGENDA_DATA_DIR=/app/data COOKIE_SECURE=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --system --create-home precision \
 && mkdir -p /app/data && chown precision:precision /app/data
COPY backend ./backend
COPY site ./site
COPY manage.py ./manage.py
USER precision
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]

