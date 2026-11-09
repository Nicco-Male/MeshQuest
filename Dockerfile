FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY meshquest ./meshquest
COPY web ./web
RUN pip install --no-cache-dir ".[postgres]" && useradd -r -u 10001 meshquest
USER meshquest
EXPOSE 8000
CMD ["uvicorn", "meshquest.app:app", "--host", "0.0.0.0", "--port", "8000"]
