# Optional image that serves a mounted Farol project over MCP (stdio), read-only.
#   docker build -f Containerfile -t farol .
#   docker run -i --rm -v "$PWD:/knowledge:ro" farol
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 farol
COPY dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir "$(ls /tmp/*.whl)[formats]" && rm -f /tmp/*.whl

USER farol
WORKDIR /knowledge
ENTRYPOINT ["farol"]
CMD ["mcp", "--project", "/knowledge"]
