FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/counsel

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libsqlcipher-dev sqlcipher \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# llama-cpp-python is optional in containers (API mode default)
RUN grep -v "llama-cpp-python" requirements.txt > req.ci.txt \
    && pip install --no-cache-dir -r req.ci.txt

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/api/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
