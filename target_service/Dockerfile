FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask==3.1.0

COPY app.py /app/app.py
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 5000
CMD ["/app/start.sh"]
