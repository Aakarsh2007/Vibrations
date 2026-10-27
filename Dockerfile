FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VL_DATA_DIR=/data
WORKDIR /app
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt && useradd --create-home app && mkdir /data && chown app:app /data
COPY vibralens ./vibralens
COPY web ./web
COPY samples ./samples
USER app
EXPOSE 8000
CMD ["uvicorn", "vibralens.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
