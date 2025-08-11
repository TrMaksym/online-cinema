FROM python:3.11.9-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    postgresql-client \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --upgrade pip
RUN pip install poetry==2.1.3

WORKDIR /app

COPY pyproject.toml poetry.lock* /app/

RUN python --version

RUN poetry cache clear --all pypi && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
