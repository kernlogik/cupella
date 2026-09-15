
# Install dependencies for development
install:
    curl -sL https://github.com/quarto-dev/quarto-cli/releases/download/v1.6.42/quarto-1.6.42-linux-amd64.tar.gz | tar -xz -C ~/.local/
    curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | bash -s -- -b ~/.local/bin

# Build from CI/CD workflow locally
act:
  act

# Generate JSONL file
test-data:
  python3 -m test.generator -n 5000 -o data/bronze/raw_stream.jsonl

# Stream data to local ingest pipeline
stream-data:
    #!/usr/bin/env bash
    set -euo pipefail
    python3 -m test.generator -n 200 | while read -r line; do
        curl -s -X POST http://127.0.0.1:8080 \
            -H "Content-Type: application/json" \
            -d "$line" > /dev/null
    done

# Build all container images locally
build:
  # Build Container Images
  podman build -t cupella-bronze container/bronze/
  podman build -t cupella-report container/report/

# BRONZE Step: Ingest raw data
bronze:
  # Run (mounts local directory ./data/bronze ein)
  podman run -d --name cupella-bronze \
    -p 8080:8080 \
    -p 9090:9090 \
    -v ./data/bronze:/data/bronze:Z \
    cupella-bronze

# SILVER Step: Check data consistency and create OLAP file.
silver:
    cd container/silver && uv run python3 -m tasks.curate

# GOLD Step: Aggregate data, Create models
gold:
    cd container/gold && \
    uv run python3 -m tasks.extract && \
    uv run python3 -m tasks.forecast

# Generate report.
report:
    podman run --rm \
        -v "$(pwd):/workspace:Z" \
        -w /workspace \
        cupella-report \
        render reports/telemetry.qmd --output-dir output

# Stop the ingestion daemon
stop:
    podman stop cupella-bronze
    -podman rm cupella-bronze
