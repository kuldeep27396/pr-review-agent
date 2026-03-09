FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pr_review_agent ./pr_review_agent
COPY README.md pyproject.toml ./

RUN mkdir -p /app/logs

EXPOSE 3000

CMD ["sh", "-c", "uvicorn pr_review_agent.main:app --host 0.0.0.0 --port ${PORT:-3000}"]
