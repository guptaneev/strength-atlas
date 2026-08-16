FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system atlas \
    && useradd --system --gid atlas --home-dir /app atlas \
    && mkdir -p /var/atlas/models \
    && chown -R atlas:atlas /app /var/atlas

COPY --chown=atlas:atlas pyproject.toml README.md alembic.ini /app/
COPY --chown=atlas:atlas src /app/src
COPY --chown=atlas:atlas migrations /app/migrations
COPY --chown=atlas:atlas scripts /app/scripts

RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.7.1+cpu" \
    && pip install .

USER atlas

EXPOSE 8000

CMD ["python", "/app/scripts/start_production.py"]
