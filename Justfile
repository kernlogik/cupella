act:
  act

test-data:
  # Generate JSONL file
  python3 -m test.generator -n 5000 -o data/bronze/raw_stream.jsonl


stream-data:
    #!/usr/bin/env bash
    set -euo pipefail
    python3 -m test.generator -n 200 | while read -r line; do
        curl -s -X POST http://localhost:8080 \
            -H "Content-Type: application/json" \
            -d "$line" > /dev/null
    done


build:
  # Build
  podman build -t cupella-bronze containers/bronze/


bronze:
  # Run (hängt das lokale Verzeichnis ./data/bronze ein)
  podman run -d --name cupella-bronze \
    -p 8080:8080 \
    -p 9090:9090 \
    -v ./data/bronze:/data/bronze:Z \
    cupella-bronze


