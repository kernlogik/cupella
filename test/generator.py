#!/usr/bin/env python3
import argparse
import json
import random
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

DEVICES = [f"sensor-{x:02d}" for x in range(1, 6)]


def generate_stream(count: int, seed: int = 42, start: datetime | None = None):
    random.seed(seed)
    current_time = start or datetime.now(timezone.utc) - timedelta(hours=count / 3600)
    last_record = None

    for _ in range(count):
        current_time += timedelta(seconds=random.randint(1, 5))

        # 1. Duplikat erzeugen (5 % Chance: exakte Kopie des letzten Events)
        if last_record and random.random() < 0.05:
            yield last_record
            continue

        # Basiswerte
        temp = round(random.gauss(21.5, 2.0), 2)
        humidity = round(random.gauss(50.0, 5.0), 1)
        status = "OK"

        # 2. Ausreisser injizieren (3 % Chance)
        if random.random() < 0.03:
            temp = random.choice([999.9, -99.0, 150.2])
            status = "SENSOR_ERR"

        # 3. Null-Werte injizieren (5 % Chance)
        if random.random() < 0.05:
            temp = None
        if random.random() < 0.03:
            humidity = None

        record = {
            "event_id": str(uuid.UUID(int=random.getrandbits(128), version=4)),
            "timestamp": current_time.isoformat(),
            "device_id": random.choice(DEVICES),
            "payload": {
                "temperature": temp,
                "humidity": humidity,
                "status": status,
            },
        }

        last_record = record
        yield record


def main():
    parser = argparse.ArgumentParser(description="Synthetic Sensor Stream Generator")
    parser.add_argument(
        "-n", "--count", type=int, default=1000, help="Anzahl der Records"
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="Zieldatei (Default: stdout)"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Seed für Reproduzierbarkeit"
    )
    parser.add_argument(
        "--start",
        type=datetime.fromisoformat,
        default=None,
        help="Startzeitpunkt ISO-8601 (Default: jetzt; für reproduzierbare Läufe setzen)",
    )
    args = parser.parse_args()
    if args.start and args.start.tzinfo is None:
        args.start = args.start.replace(tzinfo=timezone.utc)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out_file = open(args.output, "w", encoding="utf-8") if args.output else None

    try:
        for record in generate_stream(args.count, args.seed, args.start):
            line = json.dumps(record)
            if out_file:
                out_file.write(line + "\n")
            else:
                print(line)
    finally:
        if out_file:
            out_file.close()


if __name__ == "__main__":
    main()
