import asyncio
import json
from pathlib import Path
from datetime import datetime

import openpyxl
import websockets

from detector import DetectionEngine


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "NeoCare_Mixed_Same_Timestamp_NonOverlapping_Alarm_Test_Dataset.xlsx"
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
# DETECTION ENGINE
# ---------------------------------------------------------

detector = DetectionEngine()


# ---------------------------------------------------------
# BABY ADMISSION / DISCHARGE HISTORY
# ---------------------------------------------------------

def load_patient_history():

    if not HISTORY_FILE.exists():
        return []

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        return (
            data
            if isinstance(data, list)
            else []
        )

    except Exception as error:

        print(
            f"WARNING: Could not load baby history: "
            f"{error}"
        )

        return []


patient_history = load_patient_history()


def save_patient_history():

    try:

        HISTORY_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            HISTORY_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                patient_history,
                file,
                indent=4,
                ensure_ascii=False
            )

    except Exception as error:

        print(
            f"ERROR: Could not save baby history: "
            f"{error}"
        )


# ---------------------------------------------------------
# NORMALIZE INCUBATOR ID
# ---------------------------------------------------------

def normalize_incubator_id(value):

    value = str(value).strip()

    if (
        value.startswith("INC")
        and "-" not in value
    ):

        number = value[3:]

        if number.isdigit():

            return (
                f"INC-{int(number):03d}"
            )

    return value


# ---------------------------------------------------------
# LOAD EXCEL DATASET
# ---------------------------------------------------------

def load_dataset():

    if not DATA_FILE.exists():

        print(
            "ERROR: Excel dataset not found:"
        )

        print(DATA_FILE)

        return {}

    print(
        "Loading Excel dataset..."
    )

    print(DATA_FILE)

    workbook = openpyxl.load_workbook(
        DATA_FILE,
        read_only=True,
        data_only=True
    )

    sheet = workbook.active

    rows = list(
        sheet.iter_rows(
            values_only=True
        )
    )

    if not rows:

        print(
            "ERROR: Excel dataset is empty."
        )

        workbook.close()

        return {}

    headers = [

        str(value).strip()
        if value is not None
        else ""

        for value in rows[0]
    ]

    dataset = {}

    for row in rows[1:]:

        if not any(
            value is not None
            for value in row
        ):
            continue

        record = dict(
            zip(headers, row)
        )

        incubator_id = (
            normalize_incubator_id(
                record.get(
                    "Incubator ID"
                )
            )
        )

        if (
            incubator_id
            not in ACTIVE_INCUBATORS
        ):
            continue

        dataset.setdefault(
            incubator_id,
            []
        )

        dataset[
            incubator_id
        ].append(record)

    workbook.close()

    print()
    print(
        "Dataset loaded successfully."
    )

    for incubator_id in ACTIVE_INCUBATORS:

        print(
            f"{incubator_id}: "
            f"{len(dataset.get(incubator_id, []))} "
            f"readings"
        )

    return dataset


dataset = load_dataset()


# ---------------------------------------------------------
# CREATE TELEMETRY FROM DATASET
# ---------------------------------------------------------

def create_telemetry(
    incubator_id,
    tick
):

    records = dataset.get(
        incubator_id,
        []
    )

    if not records:
        return None

    record = records[
        tick % len(records)
    ]

    timestamp = record.get(
        "Timestamp"
    )

    if isinstance(
        timestamp,
        datetime
    ):

        timestamp = (
            timestamp.isoformat()
        )

    else:

        timestamp = str(timestamp)

    # -----------------------------------------------------
    # Existing dataset alarm values
    # -----------------------------------------------------

    temperature_alarm = int(
        record.get(
            "Temperature Alarm",
            0
        ) or 0
    )

    dataset_movement_alarm = int(
        record.get(
            "Movement Alarm",
            0
        ) or 0
    )

    overall_alarm = int(
        record.get(
            "Overall Alarm",
            0
        ) or 0
    )

    # -----------------------------------------------------
    # Raw telemetry record
    # -----------------------------------------------------

    return {

        "baby_id":
            str(
                record.get(
                    "Baby ID",
                    ""
                )
            ),

        "baby_name":
            str(
                record.get(
                    "Baby Name",
                    ""
                )
            ),

        "incubator_id":
            incubator_id,

        "timestamp":
            timestamp,

        "incubator_power":
            record.get(
                "Incubator Power"
            ),

        "incubator_temperature_c":
            record.get(
                "Incubator Temperature (°C)"
            ),

        "skin_temperature_c":
            record.get(
                "Baby Temperature (°C)"
            ),

        "baby_temperature_c":
            record.get(
                "Baby Temperature (°C)"
            ),

        "body_movements":
            record.get(
                "Movement"
            ),

        "movement":
            record.get(
                "Movement"
            ),

        # Existing dataset alarm
        "dataset_movement_alarm":
            dataset_movement_alarm,

        "temperature_alarm":
            temperature_alarm,

        "overall_alarm":
            overall_alarm,

        "sensor_status":
            "CONNECTED",

        "signal_quality":
            "GOOD",

        "dislodgement_flag":
            "0",

        "event":
            "ALARM"
            if overall_alarm == 1
            else "NORMAL"
    }


# ---------------------------------------------------------
# BROADCAST DATA
# ---------------------------------------------------------

async def broadcast(data):

    if not connected_clients:
        return

    message = json.dumps(
        data,
        default=str
    )

    disconnected = set()

    for client in connected_clients:

        try:

            await client.send(
                message
            )

        except Exception:

            disconnected.add(
                client
            )

    for client in disconnected:

        connected_clients.discard(
            client
        )


# ---------------------------------------------------------
# SEND HISTORY TO ONE CLIENT
# ---------------------------------------------------------

async def send_patient_history(
    websocket
):

    await websocket.send(
        json.dumps(
            {
                "type":
                    "patient_history",

                "records":
                    patient_history
            },
            default=str
        )
    )


# ---------------------------------------------------------
# REGISTER BABY
# ---------------------------------------------------------

async def register_patient(data):

    record = data.get(
        "record"
    )

    if not record:
        return

    record_id = record.get(
        "record_id"
    )

    if not record_id:

        record_id = (
            f"{record.get('baby_id', 'UNKNOWN')}_"
            f"{record.get('incubator_id', 'UNKNOWN')}_"
            f"{record.get('admitted_at', '')}"
        )

        record["record_id"] = (
            record_id
        )

    if any(
        item.get("record_id")
        == record_id
        for item in patient_history
    ):

        return

    patient_history.append(
        record
    )

    save_patient_history()

    print(
        f"[HISTORY] Baby admitted: "
        f"{record.get('baby_name')} -> "
        f"{record.get('incubator_id')}"
    )

    await broadcast(
        {
            "type":
                "patient_history",

            "records":
                patient_history
        }
    )


# ---------------------------------------------------------
# DISCHARGE BABY
# ---------------------------------------------------------

async def discharge_patient(data):

    record_id = data.get(
        "record_id"
    )

    baby_id = data.get(
        "baby_id"
    )

    incubator_id = data.get(
        "incubator_id"
    )

    discharged_at = (
        data.get(
            "discharged_at"
        )
        or datetime.now().isoformat()
    )

    record = None

    if record_id:

        for item in reversed(
            patient_history
        ):

            if (
                item.get("record_id")
                == record_id
            ):

                record = item

                break

    if record is None:

        for item in reversed(
            patient_history
        ):

            if (
                item.get(
                    "incubator_id"
                )
                == incubator_id

                and item.get(
                    "baby_id"
                )
                == baby_id

                and item.get(
                    "status"
                )
                == "ADMITTED"
            ):

                record = item

                break

    if record is None:

        print(
            f"[HISTORY] Could not find baby "
            f"to discharge from "
            f"{incubator_id}."
        )

        return

    record["status"] = (
        "DISCHARGED"
    )

    record["discharged_at"] = (
        discharged_at
    )

    save_patient_history()

    print(
        f"[HISTORY] Baby discharged: "
        f"{record.get('baby_name')} <- "
        f"{record.get('incubator_id')}"
    )

    await broadcast(
        {
            "type":
                "patient_history",

            "records":
                patient_history
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
            "type":
                "patient_history",

            "records":
                patient_history
        }
    )


# ---------------------------------------------------------
# WEBSOCKET CONNECTION
# ---------------------------------------------------------

async def handle_client(
    websocket
):

    connected_clients.add(
        websocket
    )

    print(
        f"Dashboard connected "
        f"({len(connected_clients)} "
        f"active connection)"
    )

    try:

        await send_patient_history(
            websocket
        )

        async for raw_message in websocket:

            try:

                data = json.loads(
                    raw_message
                )

            except json.JSONDecodeError:

                print(
                    "[WEBSOCKET] "
                    "Invalid JSON received."
                )

                continue

            message_type = data.get(
                "type"
            )

            if (
                message_type
                == "get_patient_history"
            ):

                await send_patient_history(
                    websocket
                )

            elif (
                message_type
                == "register_baby"
            ):

                await register_patient(
                    data
                )

            elif (
                message_type
                == "discharge_baby"
            ):

                await discharge_patient(
                    data
                )

            elif (
                message_type
                == "clear_patient_history"
            ):

                await clear_patient_history()

    except websockets.exceptions.ConnectionClosed:

        pass

    finally:

        connected_clients.discard(
            websocket
        )

        print(
            f"Dashboard disconnected "
            f"({len(connected_clients)} "
            f"active connection)"
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

        for incubator_id in (
            ACTIVE_INCUBATORS
        ):

            raw_data = create_telemetry(
                incubator_id,
                tick
            )

            if raw_data is None:

                print(
                    f"{incubator_id} | "
                    f"No dataset available"
                )

                continue

            # -------------------------------------------------
            # RUN DETECTION ENGINE
            # -------------------------------------------------

            result = detector.process(
                raw_data
            )

            # -------------------------------------------------
            # Add server information
            # -------------------------------------------------

            result["type"] = (
                "telemetry"
            )

            result["server_time"] = (
                datetime.now().isoformat()
            )

            # -------------------------------------------------
            # IMPORTANT:
            # DetectionEngine movement alarm
            # overrides the dataset movement alarm.
            #
            # Dataset alarm may already say 1,
            # but our actual requirement is:
            #
            # NO MOVEMENT FOR 1 HOUR
            # -------------------------------------------------

            result["movement_alarm"] = int(
                result.get(
                    "movement_alarm",
                    0
                )
            )

            # -------------------------------------------------
            # Overall alarm
            # -------------------------------------------------

            temperature_alarm = int(
                result.get(
                    "temperature_alarm",
                    0
                )
            )

            movement_alarm = int(
                result.get(
                    "movement_alarm",
                    0
                )
            )

            dataset_overall_alarm = int(
                result.get(
                    "overall_alarm",
                    0
                )
            )

            result["overall_alarm"] = int(
                temperature_alarm == 1
                or movement_alarm == 1
                or dataset_overall_alarm == 1
            )

            # -------------------------------------------------
            # Update final state/message
            # -------------------------------------------------

            if movement_alarm == 1:

                result["state"] = (
                    "CRITICAL"
                )

                result["message"] = (
                    "No baby movement "
                    "detected for 1 hour."
                )

                result["event"] = (
                    "MOVEMENT_ALARM"
                )

            # -------------------------------------------------
            # Send to dashboard
            # -------------------------------------------------

            await broadcast(
                result
            )

            # -------------------------------------------------
            # Terminal output
            # -------------------------------------------------

            duration_minutes = (
                result.get(
                    "no_movement_duration_minutes",
                    0
                )
            )

            print(
                f"{incubator_id} | "
                f"{result.get('state', 'UNKNOWN')} | "
                f"Skin: "
                f"{result.get('skin_temperature_c', '--')} °C | "
                f"Movement: "
                f"{result.get('movement', 0)} | "
                f"No Movement: "
                f"{duration_minutes:.1f} min | "
                f"Movement Alarm: "
                f"{result.get('movement_alarm', 0)} | "
                f"Temp Alarm: "
                f"{result.get('temperature_alarm', 0)} | "
                f"Overall Alarm: "
                f"{result.get('overall_alarm', 0)}"
            )

        tick += 1

        await asyncio.sleep(
            SEND_INTERVAL
        )


# ---------------------------------------------------------
# MAIN SERVER
# ---------------------------------------------------------

async def main():

    print(
        "=" * 70
    )

    print(
        "NeoCare Neonatal Monitoring "
        "WebSocket Server"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Dataset: {DATA_FILE}"
    )

    print(
        f"Patient history: "
        f"{HISTORY_FILE}"
    )

    print(
        f"Existing patient history "
        f"records: "
        f"{len(patient_history)}"
    )

    print()

    print(
        "All incubator slots:"
    )

    print(
        ", ".join(INCUBATORS)
    )

    print()

    print(
        "Currently active:"
    )

    print(
        ", ".join(
            ACTIVE_INCUBATORS
        )
    )

    print()

    print(
        f"WebSocket URL: "
        f"ws://{HOST}:{PORT}"
    )

    print()

    print(
        "Movement detection: "
        "1 HOUR CONTINUOUS NO-MOVEMENT"
    )

    print()

    print(
        "Waiting for dashboard "
        "connection..."
    )

    print()

    async with websockets.serve(
        handle_client,
        HOST,
        PORT
    ):

        await telemetry_stream()


# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print()

        print(
            "NeoCare server stopped."
        )