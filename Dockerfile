# syntax=docker/dockerfile:1

FROM python:3.13-slim-bookworm AS builder
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.13-slim-bookworm
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app ./app

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
