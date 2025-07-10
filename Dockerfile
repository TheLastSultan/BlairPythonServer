# 🔐 pin to a minor version you control, not "latest"
FROM python:3.12-slim-bookworm

# optional: reduce layer count & install build deps only when needed
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /usr/app

COPY requirements.txt .

RUN apt-get update \
 && apt-get install --no-install-recommends -y gcc build-essential libpq-dev \
 && pip install --upgrade pip \
 && pip install -r requirements.txt \
 && apt-get purge -y gcc build-essential \
 && apt-get autoremove -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8000

CMD ["uvicorn", "agent.recruiter_agent:app", "--host", "0.0.0.0", "--port", "8000"]