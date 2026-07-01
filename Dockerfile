# VyMCP speaks MCP over stdio, so run the container attached:
#   docker run -i --rm -e VYMANAGER_BASE_URL=... -e VYMANAGER_API_TOKEN=... vymcp
FROM python:3.12-slim

WORKDIR /app

# Install the package (build deps are fetched in an isolated PEP 517 env).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# Run as a non-root user.
RUN useradd --create-home --uid 1000 vymcp
USER vymcp

# Configuration comes from the environment (see .env.example); never baked in.
ENTRYPOINT ["vymcp"]
