import csv
import time
from pathlib import Path


# Location of the mock telemetry dataset
DATA_FILE = Path(__file__).parent.parent / "data" / "neocare_mock_telemetry.csv"


def stream_data(delay=1):
    """
    Reads the mock telemetry dataset one record at a time
    and simulates a real-time sensor data stream.
    """

    if not DATA_FILE.exists():
        print(f"ERROR: Dataset not found:")
        print(DATA_FILE)
        return

    print("=" * 60)
    print("NEOCARE REAL-TIME TELEMETRY SIMULATOR")
    print("=" * 60)
    print(f"Dataset: {DATA_FILE}")
    print(f"Update interval: {delay} second(s)")
    print("Press CTRL+C to stop.")
    print("=" * 60)

    try:
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as file:

            reader = csv.DictReader(file)

            for record in reader:

                print("\n----------------------------------------")

                print(f"Time           : {record['timestamp']}")
                print(f"Incubator      : {record['incubator_id']}")
                print(
                    f"Skin Temp      : "
                    f"{record['skin_temperature_c']} °C"
                )
                print(
                    f"Air Temp       : "
                    f"{record['air_temperature_c']} °C"
                )
                print(
                    f"Probe Status   : "
                    f"{record['sensor_status']}"
                )
                print(
                    f"Signal Quality : "
                    f"{record['signal_quality']}"
                )
                print(
                    f"Dislodgement   : "
                    f"{record['dislodgement_flag']}"
                )
                print(f"Event          : {record['event']}")

                time.sleep(delay)

    except KeyboardInterrupt:
        print("\n\nSimulation stopped.")

    except Exception as error:
        print(f"\nERROR: {error}")


if __name__ == "__main__":
    stream_data(delay=1)
    