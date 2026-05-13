FROM python:3.11-slim

WORKDIR /app

# Instalar dependências necessárias do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Adicionar gunicorn caso não exista no requirements
RUN pip install --no-cache-dir gunicorn==21.2.0

# Copiar todo o código fonte
COPY . .

# A porta padrão do Render
ENV PORT=5000

# Executar via Gunicorn (Servidor WSGI para Produção)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"]
