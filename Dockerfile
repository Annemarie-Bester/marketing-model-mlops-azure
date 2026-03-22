FROM python:3.12-slim

# Run as non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install dependencies in a separate layer so it's cached on code-only changes.
# Note: requirements.txt includes dev tools (jupyter, pytest) for simplicity.
# In production, split into requirements-prod.txt to reduce image size.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and config
COPY src/ src/
COPY config.yaml .

# Copy the trained model artifact baked into the image at build time.
# The CI pipeline runs training before docker build so this file exists.
COPY artifacts/model.pkl artifacts/model.pkl

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
