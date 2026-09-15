+++
title = "Architektur & Pipeline-Doku"
+++

Willkommen bei **Cupella**.

### Medallion Flow
1. **Bronze:** Unstrukturierte JSON-Events via Vector HTTP-Server.
2. **Silver:** Bereinigung, Typisierung und Parquet-Deduplizierung via Polars.
3. **Gold:** Verdichtung mit DuckDB & 3h-Inferenz.
4. **Reporting:** Reproduzierbare HTML- & PDF-Artefakte via Quarto & Typst.

```mermaid
flowchart TD
    subgraph Ingestion ["Ingestion & Edge"]
        Gen["Sensor Clients / Generator"] -->|HTTP POST :8080| Vec["Vector Daemon (Podman)"]
    end

    subgraph Bronze ["Bronze Layer (Raw)"]
        Vec -->|Stream / Append-Only| B_Files[("data/bronze/*.jsonl<br/>Raw Events Envelope")]
    end

    subgraph Silver ["Silver Layer (Curated)"]
        B_Files -->|Read & Parse| Pol["Polars Cleaner (Podman)"]
        Pol -->|Dedup & Outlier Filtering| S_Parquet[("data/silver/*.parquet<br/>Typisierte Events")]
        Pol -->|Metriken / Jinja2| Audit["data/silver/report.html<br/>(Audit Dashboard)"]
    end

    subgraph Gold ["Gold Layer (Aggregation & ML)"]
        S_Parquet -->|Window Aggregates| DDB["DuckDB SQL"]
        DDB --> G_Hourly[("data/gold/sensor_hourly.parquet")]
        G_Hourly -->|Lags & Ridge-Modell| ML["tasks/forecast.py"]
        ML --> G_Forecast[("data/gold/sensor_forecast.parquet")]
    end

    subgraph Serving ["Serving & Presentation"]
        G_Hourly & G_Forecast --> Q["Quarto + Typst (Podman)"]
        Q --> R_HTML["reports/output/telemetry.html"]
        Q --> R_PDF["reports/output/telemetry.pdf"]
        Zola["Zola Build"] --> D_Pub["docs/public/"]
        
        Audit --> Caddy["Caddy Hub (:3000)"]
        R_HTML --> Caddy
        R_PDF --> Caddy
        D_Pub --> Caddy
    end

    classDef storage fill:#f1f5f9,stroke:#64748b,stroke-width:1px;
    classDef compute fill:#eff6ff,stroke:#2563eb,stroke-width:1px;
    class B_Files,S_Parquet,G_Hourly,G_Forecast storage;
    class Vec,Pol,DDB,ML,Q,Zola,Caddy compute;
```
