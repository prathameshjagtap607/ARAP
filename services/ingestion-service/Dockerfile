FROM python:3.11-slim

WORKDIR /app

COPY services/ingestion-service/pyproject.toml pyproject.toml
RUN pip install --no-cache-dir -e .

COPY services/ingestion-service/src/ src/
COPY agents/ agents/

ENV PYTHONPATH="/app"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
