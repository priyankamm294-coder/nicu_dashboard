import asyncio
import csv
import json
from pathlib import Path
from datetime import datetime

import websockets

from detector import DetectionEngine


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "neocare_mock_telemetry.csv"


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

HOST = "localhost"
PORT = 8765
SEND_INTERVAL = 1.0

INCUBATORS = [
    "INC-001",
    "INC-002",
    "INC-003",
    "INC-004",
    "INC-005",
    "INC-006",
    "INC-007",
    "INC-008",
    "INC-009",
    "INC-010",
]


# ---------------------------------------------------------
# CONNECTED DASHBOARDS
# ---------------------------------------------------------

connected_clients = set()


# ---------------------------------------------------------
# DETECTION ENGINE
# ---------------------------------------------------------

detector = DetectionEngine()


# ---------------------------------------------------------
# LOAD EXISTING DATA
# ---------------------------------------------------------

def load_dataset():
    if not DATA_FILE.exists():
        print("ERROR: Dataset not found:")
        print(DATA_FILE)
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


dataset = load_dataset()


# ---------------------------------------------------------
# CREATE TELEMETRY FOR 10 INCUBATORS
# ---------------------------------------------------------

def create_telemetry(incubator_id, tick):
    """
    Creates simulation telemetry for all 10 incubators.

    INC-001 to INC-004:
        Uses the existing mock dataset.

    INC-005 to INC-010:
        Uses generated simulation values.
    """

    # -----------------------------------------------------
    # Use existing dataset for INC-001 to INC-004
    # -----------------------------------------------------

    matching_rows = [
        row for row in dataset
        if row.get("incubator_id") == incubator_id
    ]

    if matching_rows:
        row = matching_rows[tick % len(matching_rows)].copy()

    else:
        # -------------------------------------------------
        # Generate telemetry for INC-005 to INC-010
        # -------------------------------------------------

        import math
        import random

        base_temperature = {
            "INC-005": 36.60,
            "INC-006": 36.55,
            "INC-007": 36.65,
            "INC-008": 36.58,
            "INC-009": 36.62,
            "INC-010": 36.57,
        }.get(incubator_id, 36.60)

        base_movements = {
            "INC-005": 6,
            "INC-006": 8,
            "INC-007": 5,
            "INC-008": 9,
            "INC-009": 7,
            "INC-010": 6,
        }.get(incubator_id, 7)

        variation = math.sin(tick / 4) * 0.08

        skin_temperature = base_temperature + variation

        body_movements = max(
            0,
            base_movements + random.randint(-3, 3)
        )

        row = {
            "timestamp": datetime.now().isoformat(),
            "incubator_id": incubator_id,
            "skin_temperature_c": f"{skin_temperature:.2f}",
            "body_movements": str(body_movements),
            "dislodgement_flag": "0",
            "sensor_status": "CONNECTED",
            "signal_quality": "GOOD",
            "event": "NORMAL",
            "simulation_mode": "NORMAL",
            "data_valid": "1",
        }

    return row


# ---------------------------------------------------------
# WEBSOCKET CONNECTION HANDLER
# ---------------------------------------------------------

async def handle_client(websocket):

    connected_clients.add(websocket)

    print(
        f"Dashboard connected "
        f"({len(connected_clients)} active connection)"
    )

    try:
        await websocket.wait_closed()

    finally:
        connected_clients.discard(websocket)

        print(
            f"Dashboard disconnected "
            f"({len(connected_clients)} active connection)"
        )


# ---------------------------------------------------------
# SEND DATA TO DASHBOARDS
# ---------------------------------------------------------

async def broadcast(data):

    if not connected_clients:
        return

    message = json.dumps(data)

    disconnected = set()

    for client in connected_clients:

        try:
            await client.send(message)

        except Exception:
            disconnected.add(client)

    for client in disconnected:
        connected_clients.discard(client)


# ---------------------------------------------------------
# TELEMETRY STREAM
# ---------------------------------------------------------

async def telemetry_stream():

    tick = 0

    while True:

        for incubator_id in INCUBATORS:

            row = create_telemetry(
                incubator_id,
                tick
            )

            # Run detection engine
            result = detector.process(row)

            # Add server information
            result["type"] = "telemetry"
            result["server_time"] = datetime.now().isoformat()

            # Send to dashboard
            await broadcast(result)

            # Terminal display
            print(
                f"{incubator_id} | "
                f"{result.get('state', 'UNKNOWN')} | "
                f"Skin: "
                f"{result.get('skin_temperature_c', '--')} °C | "
                f"Movements: "
                f"{result.get('body_movements', '--')} | "
                f"Probe: "
                f"{result.get('sensor_status', '--')}"
            )

            await asyncio.sleep(SEND_INTERVAL)

        tick += 1


# ---------------------------------------------------------
# MAIN SERVER
# ---------------------------------------------------------

async def main():

    print("=" * 60)
    print("NeoCare Neonatal Monitoring WebSocket Server")
    print("=" * 60)

    print()
    print("WebSocket URL:")
    print(f"ws://{HOST}:{PORT}")

    print()
    print("Supported incubators:")
    print(", ".join(INCUBATORS))

    print()
    print("Waiting for dashboard connection...")
    print()

    async with websockets.serve(
        handle_client,
        HOST,
        PORT
    ):

        await telemetry_stream()


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        print()
        print("NeoCare server stopped.")