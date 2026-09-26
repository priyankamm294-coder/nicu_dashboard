import csv
import time
from pathlib import Path

from detector import DetectionEngine


# ---------------------------------------------------------
# File location
# ---------------------------------------------------------

DATA_FILE = (
    Path(__file__).parent.parent
    / "data"
    / "neocare_mock_telemetry.csv"
)


# ---------------------------------------------------------
# Main real-time processing
# ---------------------------------------------------------

def run_system(delay=1):

    if not DATA_FILE.exists():

        print("ERROR: Dataset not found.")
        print(DATA_FILE)
        return

    detector = DetectionEngine()

    print("=" * 70)
    print("NEOCARE REAL-TIME MONITORING SYSTEM")
    print("=" * 70)

    print(f"Dataset : {DATA_FILE}")
    print(f"Interval: {delay} second(s)")
    print("Press CTRL+C to stop.")

    print("=" * 70)

    try:

        with open(
            DATA_FILE,
            "r",
            newline="",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            for record in reader:

                # -----------------------------------------
                # Send telemetry to detection engine
                # -----------------------------------------

                result = detector.process(record)

                # -----------------------------------------
                # Display result
                # -----------------------------------------

                print()
                print("-" * 70)

                print(
                    f"TIME       : "
                    f"{result['timestamp']}"
                )

                print(
                    f"INCUBATOR  : "
                    f"{result['incubator_id']}"
                )

                print(
                    f"SKIN TEMP  : "
                    f"{result['skin_temperature_c']} °C"
                )

                print(
                    f"MOVEMENTS  : "
                    f"{result['body_movements']}"
                )

                print(
                    f"PROBE      : "
                    f"{result['sensor_status']}"
                )

                print(
                    f"SIGNAL     : "
                    f"{result['signal_quality']}"
                )

                print(
                    f"EVENT      : "
                    f"{result['event']}"
                )

                print(
                    f"RATE       : "
                    f"{result['rate_of_change_c']} °C"
                )

                print(
                    f"STATE      : "
                    f"{result['state']}"
                )

                print(
                    f"MESSAGE    : "
                    f"{result['message']}"
                )

                time.sleep(delay)

    except KeyboardInterrupt:

        print()
        print("=" * 70)
        print("NEOCARE SYSTEM STOPPED")
        print("=" * 70)

    except Exception as error:

        print()
        print("SYSTEM ERROR:")
        print(error)


# ---------------------------------------------------------
# Program entry point
# ---------------------------------------------------------

if __name__ == "__main__":

    run_system(delay=1)