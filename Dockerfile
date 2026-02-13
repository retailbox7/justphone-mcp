FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir "fastmcp>=2.14.0,<3" "mysql-connector-python>=9.0.0"

COPY . .

EXPOSE 8000

CMD ["python", "server.py"]
