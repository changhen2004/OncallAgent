FROM python:3.12-alpine

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project

COPY prometheusTestServer ./prometheusTestServer

EXPOSE 2112
CMD [".venv/bin/python", "prometheusTestServer/main.py"]
