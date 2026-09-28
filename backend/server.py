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
    / "NeoCare_4_Babies_5_Second_Mixed_Dummy_Dataset.xlsx"
)


# ---------------------------------------------------------
# SERVER SETTINGS
# ---------------------------------------------------------

HOST = "localhost"
PORT = 8765

# One dataset reading every second
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
# CONVERT EXCEL INCUBATOR ID
# ---------------------------------------------------------

def normalize_incubator_id(value):

    value = str(value).strip()

    # INC001 → INC-001
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
        data_only=True
    )


    sheet = workbook.active


    rows = list(
        sheet.iter_rows(
            values_only=True
        )
    )


    if not rows:

        print("ERROR: Excel dataset is empty.")

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


        incubator_id = normalize_incubator_id(
            record.get("Incubator ID")
        )


        # Only load the four active incubators
        if incubator_id not in ACTIVE_INCUBATORS:
            continue


        if incubator_id not in dataset:

            dataset[incubator_id] = []


        dataset[incubator_id].append(
            record
        )


    workbook.close()


    print()
    print("Dataset loaded successfully.")

    for incubator_id in ACTIVE_INCUBATORS:

        print(
            f"{incubator_id}: "
            f"{len(dataset.get(incubator_id, []))} readings"
        )


    return dataset


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

dataset = load_dataset()


# ---------------------------------------------------------
# CREATE TELEMETRY FROM REAL DATASET
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


    # Cycle through the 300 readings
    record = records[
        tick % len(records)
    ]


    # -----------------------------------------------------
    # Timestamp
    # -----------------------------------------------------

    timestamp = record.get(
        "Timestamp"
    )


    if isinstance(
        timestamp,
        datetime
    ):

        timestamp = timestamp.isoformat()

    else:

        timestamp = str(
            timestamp
        )


    # -----------------------------------------------------
    # Alarm values
    # -----------------------------------------------------

    temperature_alarm = int(
        record.get(
            "Temperature Alarm",
            0
        ) or 0
    )


    movement_alarm = int(
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
    # State
    # -----------------------------------------------------

    if overall_alarm == 1:

        state = "WARNING"

        message = "Alarm detected in dataset."

    else:

        state = "NORMAL"

        message = "Telemetry operating normally."


    # -----------------------------------------------------
    # Create dashboard-compatible record
    # -----------------------------------------------------

    return {

        # Dataset identity
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

        # Dashboard incubator format
        "incubator_id":
            incubator_id,

        # Original dataset timestamp
        "timestamp":
            timestamp,

        # Incubator information
        "incubator_power":
            record.get(
                "Incubator Power"
            ),

        "incubator_temperature_c":
            record.get(
                "Incubator Temperature (°C)"
            ),

        # Baby temperature
        # Map this to the existing frontend field
        "skin_temperature_c":
            record.get(
                "Baby Temperature (°C)"
            ),

        "baby_temperature_c":
            record.get(
                "Baby Temperature (°C)"
            ),

        # Movement
        "body_movements":
            record.get(
                "Movement"
            ),

        "movement":
            record.get(
                "Movement"
            ),

        # Actual dataset alarms
        "temperature_alarm":
            temperature_alarm,

        "movement_alarm":
            movement_alarm,

        "overall_alarm":
            overall_alarm,

        # Existing frontend-compatible fields
        "movement_status":
            (
                "ALARM"
                if movement_alarm == 1
                else "NORMAL"
            ),

        "sensor_status":
            "CONNECTED",

        "signal_quality":
            "GOOD",

        "dislodgement_flag":
            "0",

        "event":
            (
                "ALARM"
                if overall_alarm == 1
                else "NORMAL"
            ),

        # State
        "state":
            state,

        "message":
            message,

        "rate_of_change_c":
            None,

        # Server time
        "server_time":
            datetime.now().isoformat(),

        "type":
            "telemetry",
    }


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
        f"({len(connected_clients)} active connection)"
    )


    try:

        await websocket.wait_closed()


    finally:

        connected_clients.discard(
            websocket
        )


        print(
            f"Dashboard disconnected "
            f"({len(connected_clients)} active connection)"
        )


# ---------------------------------------------------------
# BROADCAST DATA
# ---------------------------------------------------------

async def broadcast(
    data
):

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


        # Send one reading for each
        # of the four active incubators
        for incubator_id in ACTIVE_INCUBATORS:

            data = create_telemetry(
                incubator_id,
                tick
            )


            if data is None:

                print(
                    f"{incubator_id} | "
                    f"No dataset available"
                )

                continue


            await broadcast(
                data
            )


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


        # Move to next dataset row
        tick += 1


        # Wait one second
        await asyncio.sleep(
            SEND_INTERVAL
        )


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
    print(
        f"Dataset: {DATA_FILE}"
    )


    print()
    print("All incubator slots:")

    print(
        ", ".join(
            INCUBATORS
        )
    )


    print()
    print("Currently active:")

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
        "Waiting for dashboard connection..."
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