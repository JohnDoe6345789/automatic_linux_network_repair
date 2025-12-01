# automatic_linux_network_repair: Choose a base image
FROM python:3.11-slim

# automatic_linux_network_repair: Set working directory
WORKDIR /app

# automatic_linux_network_repair: Copy project files
COPY pyproject.toml /app/
COPY src/ /app/src/

# automatic_linux_network_repair: Install dependencies
RUN pip install --no-cache-dir .

# automatic_linux_network_repair: Set environment variables
ENV APP_ENV=automatic_linux_network_repair_env

# automatic_linux_network_repair: Expose port if needed
EXPOSE 8000

# automatic_linux_network_repair: Define default command
CMD ["python", "-m", "automatic_linux_network_repair"]
