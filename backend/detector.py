
from datetime import datetime


class DetectionEngine:
    """
    NeoCare Detection Engine

    Movement frequency:
        Below 10 Hz  -> Movement alarm
        10-20 Hz     -> Normal
        Above 20 Hz  -> Movement alarm

    Baby temperature:
        Below 36.5 C -> Low temperature alarm
        36.5-37.5 C  -> Normal
        Above 37.5 C -> High temperature alarm

    The original movement frequency is preserved in the
    output. This is a software simulation, not a clinical
    monitoring or alarm system.
    """

    LOW_TEMPERATURE = 36.5
    HIGH_TEMPERATURE = 37.5

    LOW_MOVEMENT_FREQUENCY = 10.0
    HIGH_MOVEMENT_FREQUENCY = 20.0

    def __init__(self):
        self.previous_skin_temperature = {}

    @staticmethod
    def _to_float(value):
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_timestamp(value):
        if isinstance(value, datetime):
            return value

        if value is None:
            return None

        try:
            return datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except (ValueError, TypeError):
            return None

    def process(self, record):
        incubator_id = record.get("incubator_id", "UNKNOWN")

        temperature = self._to_float(
            record.get("baby_temperature_c",
                       record.get("skin_temperature_c"))
        )

        # The dataset's Movement column contains frequency in Hz.
        movement_frequency = self._to_float(
            record.get("body_movements",
                       record.get("movement"))
        )

        sensor_status = record.get("sensor_status", "CONNECTED")
        signal_quality = record.get("signal_quality", "GOOD")

        dislodged = (
            str(record.get("dislodgement_flag", "0")) == "1"
            or sensor_status == "DISLODGED"
        )

        # Calculate temperature alarm from actual temperature.
        temperature_alarm = int(
            temperature is not None
            and (
                temperature < self.LOW_TEMPERATURE
                or temperature > self.HIGH_TEMPERATURE
            )
        )

        # Calculate movement alarm from frequency in Hz.
        movement_alarm = int(
            movement_frequency is not None
            and (
                movement_frequency < self.LOW_MOVEMENT_FREQUENCY
                or movement_frequency > self.HIGH_MOVEMENT_FREQUENCY
            )
        )

        if movement_frequency is None:
            movement_status = "UNKNOWN"
        elif movement_alarm:
            movement_status = (
                "LOW"
                if movement_frequency < self.LOW_MOVEMENT_FREQUENCY
                else "HIGH"
            )
        else:
            movement_status = "NORMAL"

        previous_temperature = self.previous_skin_temperature.get(
            incubator_id
        )

        rate_of_change = None

        if temperature is not None:
            if previous_temperature is not None:
                rate_of_change = round(
                    temperature - previous_temperature, 2
                )

            self.previous_skin_temperature[incubator_id] = temperature

        overall_alarm = int(
            temperature_alarm or movement_alarm or dislodged
        )

        if sensor_status == "ERROR" or signal_quality == "LOST":
            state = "SENSOR_ERROR"
            message = "Sensor data unavailable."
        elif dislodged:
            state = "CRITICAL"
            message = "Temperature probe dislodgement detected."
        elif temperature_alarm and movement_alarm:
            state = "CRITICAL"
            if temperature < self.LOW_TEMPERATURE:
                message = "Low temperature and movement alarm."
            else:
                message = "High temperature and movement alarm."
        elif temperature_alarm:
            state = "CRITICAL"
            if temperature < self.LOW_TEMPERATURE:
                message = "Low temperature alarm."
            else:
                message = "High temperature alarm."
        elif movement_alarm:
            state = "CRITICAL"
            message = "Movement frequency alarm."
        elif signal_quality == "POOR":
            state = "WARNING"
            message = "Poor sensor signal quality."
        elif temperature is None or movement_frequency is None:
            state = "SENSOR_ERROR"
            message = "Temperature or movement frequency unavailable."
        else:
            state = "NORMAL"
            message = "Telemetry operating normally."

        # Preserve original fields while providing consistent
        # names for the frontend.
        result = dict(record)

        result.update({
            "incubator_id": incubator_id,
            "baby_temperature_c": temperature,
            "skin_temperature_c": (
                self._to_float(record.get("skin_temperature_c"))
                if record.get("skin_temperature_c") is not None
                else temperature
            ),

            # IMPORTANT: preserve frequency; do not convert it to 1/0.
            "movement": movement_frequency,
            "body_movements": movement_frequency,

            "temperature_alarm": temperature_alarm,
            "movement_alarm": movement_alarm,
            "overall_alarm": overall_alarm,
            "movement_status": movement_status,
            "state": state,
            "message": message,
            "rate_of_change_c": rate_of_change,
            "no_movement_duration_seconds": 0,
            "no_movement_duration_minutes": 0,
            "sensor_status": sensor_status,
            "signal_quality": signal_quality,
            "dislodgement_flag": str(
                record.get("dislodgement_flag", "0")
            ),
        })

        return result
