FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config.yaml.example .

EXPOSE 5001

CMD ["sh", "-c", "[ -f config.yaml ] || cp config.yaml.example config.yaml; python -m app.main"]
