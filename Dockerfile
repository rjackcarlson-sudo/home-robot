FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

RUN pip install --no-cache-dir .

CMD ["python", "-m", "home_robot", "-c", "config/robot.example.yaml"]
