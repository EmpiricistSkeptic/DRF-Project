FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip --root_user_action=ignore \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000"]
