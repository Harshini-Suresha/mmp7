FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: OpenBabel (docking pipeline) + libs RDKit needs on slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    openbabel \
    libx11-6 libxext6 libxrender1 libxcb1 libxau6 libxdmcp6 \
    libgl1 libglib2.0-0 libsm6 libxcomposite1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "docking_lab_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
