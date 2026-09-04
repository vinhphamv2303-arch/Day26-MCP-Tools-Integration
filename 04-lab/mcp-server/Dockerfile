# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy application code
COPY weather.py ./

# Expose port (Cloud Run will override this)
EXPOSE 8080

# Set environment variables. Cloud Run may override PORT at runtime.
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

# Run the application
CMD ["python", "weather.py"]
