# iitk-grade-bot/bot/Dockerfile
FROM python:3.11-slim

ENV PYTHONPATH=/app
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY ./bot/ /app/

# Simplified CMD - Python should find main.py in the WORKDIR
CMD ["python", "main.py"]