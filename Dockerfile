# Two ways to run this image:
#   stdio (one user, attached):   docker run -i --rm -e VYMANAGER_BASE_URL=... \
#                                   -e VYMANAGER_API_TOKEN=... vymcp
#   http  (shared server):        docker run -d -p 8080:8080 -e VYMCP_TRANSPORT=http \
#                                   -e VYMANAGER_BASE_URL=... vymcp   (see docker-compose.yml)
FROM python:3.12-slim

WORKDIR /app

# Install the package (build deps are fetched in an isolated PEP 517 env).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# Bind to all interfaces in http mode so the published port is reachable
# (ignored by stdio mode). Configuration otherwise comes from the environment.
ENV VYMCP_HOST=0.0.0.0
EXPOSE 8080

# Run as a non-root user.
RUN useradd --create-home --uid 1000 vymcp
USER vymcp

ENTRYPOINT ["vymcp"]
