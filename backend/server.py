import asyncio
import json
from pathlib import Path
from datetime import datetime

import openpyxl
import websockets


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "NeoCare_4_Babies_5_Second_Staggered_Alarm_Dataset.xlsx"
)

HISTORY_FILE = (
    BASE_DIR
    / "data"
    / "baby_history.json"
)


# ---------------------------------------------------------
# SERVER SETTINGS
# ---------------------------------------------------------

HOST = "localhost"
PORT = 8765
SEND_INTERVAL = 1.0


# ---------------------------------------------------------
# ALL 10 INCUBATORS
# ---------------------------------------------------------

INCUBATORS = [
    "INC-001", "INC-002", "INC-003", "INC-004", "INC-005",
    "INC-006", "INC-007", "INC-008", "INC-009", "INC-010",
]


# ---------------------------------------------------------
# CURRENTLY ACTIVE INCUBATORS
# ---------------------------------------------------------

ACTIVE_INCUBATORS = [
    "INC-001",
    "INC-002",
    "INC-003",
    "INC-004",
]


# ---------------------------------------------------------
# CONNECTED DASHBOARDS
# ---------------------------------------------------------

connected_clients = set()


# ---------------------------------------------------------
# BABY ADMISSION / DISCHARGE HISTORY
# ---------------------------------------------------------

def load_patient_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except Exception as error:
        print(f"WARNING: Could not load baby history: {error}")
        return []


patient_history = load_patient_history()


def save_patient_history():
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump(patient_history, file, indent=4, ensure_ascii=False)
    except Exception as error:
        print(f"ERROR: Could not save baby history: {error}")


# ---------------------------------------------------------
# CONVERT EXCEL INCUBATOR ID
# ---------------------------------------------------------

def normalize_incubator_id(value):
    value = str(value).strip()

    if value.startswith("INC") and "-" not in value:
        number = value[3:]
        if number.isdigit():
            return f"INC-{int(number):03d}"

    return value


# ---------------------------------------------------------
# LOAD EXCEL DATASET
# ---------------------------------------------------------

def load_dataset():
    if not DATA_FILE.exists():
        print("ERROR: Excel dataset not found:")
        print(DATA_FILE)
        return {}

    print("Loading Excel dataset...")
    print(DATA_FILE)

    workbook = openpyxl.load_workbook(
        DATA_FILE,
        read_only=True,
        data_only=True,
    )

    sheet = workbook.active

    rows = list(
        sheet.iter_rows(values_only=True)
    )

    if not rows:
        print("ERROR: Excel dataset is empty.")
        workbook.close()
        return {}

    headers = [
        str(value).strip() if value is not None else ""
        for value in rows[0]
    ]

    dataset = {}

    for row in rows[1:]:
        if not any(value is not None for value in row):
            continue

        record = dict(zip(headers, row))

        incubator_id = normalize_incubator_id(
            record.get("Incubator ID")
        )

        if incubator_id not in ACTIVE_INCUBATORS:
            continue

        dataset.setdefault(incubator_id, [])
        dataset[incubator_id].append(record)

    workbook.close()

    print()
    print("Dataset loaded successfully.")

    for incubator_id in ACTIVE_INCUBATORS:
        print(
            f"{incubator_id}: "
            f"{len(dataset.get(incubator_id, []))} readings"
        )

    return dataset


dataset = load_dataset()


# ---------------------------------------------------------
# CREATE TELEMETRY FROM REAL DATASET
# ---------------------------------------------------------

def create_telemetry(incubator_id, tick):
    records = dataset.get(incubator_id, [])

    if not records:
        return None

    record = records[tick % len(records)]

    timestamp = record.get("Timestamp")

    if isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat()
    else:
        timestamp = str(timestamp)

    temperature_alarm = int(
        record.get("Temperature Alarm", 0) or 0
    )

    movement_alarm = int(
        record.get("Movement Alarm", 0) or 0
    )

    overall_alarm = int(
        record.get("Overall Alarm", 0) or 0
    )

    if overall_alarm == 1:
        state = "WARNING"
        message = "Alarm detected in dataset."
    else:
        state = "NORMAL"
        message = "Telemetry operating normally."

    return {
        "baby_id": str(record.get("Baby ID", "")),
        "baby_name": str(record.get("Baby Name", "")),
        "incubator_id": incubator_id,
        "timestamp": timestamp,
        "incubator_power": record.get("Incubator Power"),
        "incubator_temperature_c": record.get("Incubator Temperature (°C)"),
        "skin_temperature_c": record.get("Baby Temperature (°C)"),
        "baby_temperature_c": record.get("Baby Temperature (°C)"),
        "body_movements": record.get("Movement"),
        "movement": record.get("Movement"),
        "temperature_alarm": temperature_alarm,
        "movement_alarm": movement_alarm,
        "overall_alarm": overall_alarm,
        "movement_status": "ALARM" if movement_alarm == 1 else "NORMAL",
        "sensor_status": "CONNECTED",
        "signal_quality": "GOOD",
        "dislodgement_flag": "0",
        "event": "ALARM" if overall_alarm == 1 else "NORMAL",
        "state": state,
        "message": message,
        "rate_of_change_c": None,
        "server_time": datetime.now().isoformat(),
        "type": "telemetry",
    }


# ---------------------------------------------------------
# BROADCAST DATA
# ---------------------------------------------------------

async def broadcast(data):
    if not connected_clients:
        return

    message = json.dumps(data, default=str)
    disconnected = set()

    for client in connected_clients:
        try:
            await client.send(message)
        except Exception:
            disconnected.add(client)

    for client in disconnected:
        connected_clients.discard(client)


# ---------------------------------------------------------
# SEND HISTORY TO ONE CLIENT
# ---------------------------------------------------------

async def send_patient_history(websocket):
    await websocket.send(
        json.dumps(
            {
                "type": "patient_history",
                "records": patient_history,
            },
            default=str,
        )
    )


# ---------------------------------------------------------
# REGISTER BABY
# ---------------------------------------------------------

async def register_patient(data):
    record = data.get("record")

    if not record:
        return

    record_id = record.get("record_id")

    if not record_id:
        record_id = (
            f"{record.get('baby_id', 'UNKNOWN')}_"
            f"{record.get('incubator_id', 'UNKNOWN')}_"
            f"{record.get('admitted_at', '')}"
        )
        record["record_id"] = record_id

    if any(
        item.get("record_id") == record_id
        for item in patient_history
    ):
        return

    patient_history.append(record)
    save_patient_history()

    print(
        f"[HISTORY] Baby admitted: "
        f"{record.get('baby_name')} -> "
        f"{record.get('incubator_id')}"
    )

    await broadcast(
        {
            "type": "patient_history",
            "records": patient_history,
        }
    )


# ---------------------------------------------------------
# DISCHARGE BABY
# ---------------------------------------------------------

async def discharge_patient(data):
    record_id = data.get("record_id")
    baby_id = data.get("baby_id")
    incubator_id = data.get("incubator_id")
    discharged_at = (
        data.get("discharged_at")
        or datetime.now().isoformat()
    )

    record = None

    if record_id:
        for item in reversed(patient_history):
            if item.get("record_id") == record_id:
                record = item
                break

    if record is None:
        for item in reversed(patient_history):
            if (
                item.get("incubator_id") == incubator_id
                and item.get("baby_id") == baby_id
                and item.get("status") == "ADMITTED"
            ):
                record = item
                break

    if record is None:
        print(
            f"[HISTORY] Could not find baby "
            f"to discharge from {incubator_id}."
        )
        return

    record["status"] = "DISCHARGED"
    record["discharged_at"] = discharged_at

    save_patient_history()

    print(
        f"[HISTORY] Baby discharged: "
        f"{record.get('baby_name')} <- "
        f"{record.get('incubator_id')}"
    )

    await broadcast(
        {
            "type": "patient_history",
            "records": patient_history,
        }
    )


# ---------------------------------------------------------
# CLEAR HISTORY
# ---------------------------------------------------------

async def clear_patient_history():
    patient_history.clear()
    save_patient_history()

    await broadcast(
        {
            "type": "patient_history",
            "records": patient_history,
        }
    )


# ---------------------------------------------------------
# WEBSOCKET CONNECTION
# ---------------------------------------------------------

async def handle_client(websocket):
    connected_clients.add(websocket)

    print(
        f"Dashboard connected "
        f"({len(connected_clients)} active connection)"
    )

    try:
        # Send existing history immediately.
        await send_patient_history(websocket)

        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                print("[WEBSOCKET] Invalid JSON received.")
                continue

            message_type = data.get("type")

            if message_type == "get_patient_history":
                await send_patient_history(websocket)

            elif message_type == "register_baby":
                await register_patient(data)

            elif message_type == "discharge_baby":
                await discharge_patient(data)

            elif message_type == "clear_patient_history":
                await clear_patient_history()

    except websockets.exceptions.ConnectionClosed:
        pass

    finally:
        connected_clients.discard(websocket)

        print(
            f"Dashboard disconnected "
            f"({len(connected_clients)} active connection)"
        )


# ---------------------------------------------------------
# TELEMETRY STREAM
# ---------------------------------------------------------

async def telemetry_stream():
    tick = 0

    while True:
        print()
        print(
            f"========== DATASET READING "
            f"{tick + 1} =========="
        )

        for incubator_id in ACTIVE_INCUBATORS:
            data = create_telemetry(
                incubator_id,
                tick,
            )

            if data is None:
                print(
                    f"{incubator_id} | "
                    f"No dataset available"
                )
                continue

            await broadcast(data)

            print(
                f"{incubator_id} | "
                f"{data['baby_name']} | "
                f"Baby Temp: "
                f"{data['baby_temperature_c']} °C | "
                f"Movement: "
                f"{data['movement']} | "
                f"Temp Alarm: "
                f"{data['temperature_alarm']} | "
                f"Movement Alarm: "
                f"{data['movement_alarm']} | "
                f"Overall Alarm: "
                f"{data['overall_alarm']}"
            )

        tick += 1

        await asyncio.sleep(SEND_INTERVAL)


# ---------------------------------------------------------
# MAIN SERVER
# ---------------------------------------------------------

async def main():
    print("=" * 70)
    print(
        "NeoCare Neonatal Monitoring "
        "WebSocket Server"
    )
    print("=" * 70)
    print()

    print(f"Dataset: {DATA_FILE}")
    print(f"Patient history: {HISTORY_FILE}")
    print(
        f"Existing patient history records: "
        f"{len(patient_history)}"
    )
    print()

    print("All incubator slots:")
    print(", ".join(INCUBATORS))
    print()

    print("Currently active:")
    print(", ".join(ACTIVE_INCUBATORS))
    print()

    print(
        f"WebSocket URL: ws://{HOST}:{PORT}"
    )
    print()
    print("Waiting for dashboard connection...")
    print()

    async with websockets.serve(
        handle_client,
        HOST,
        PORT,
    ):
        await telemetry_stream()


# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        print("NeoCare server stopped.")
