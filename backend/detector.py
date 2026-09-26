class DetectionEngine:
    """
    Processes telemetry data and determines the
    current monitoring state.

    NOTE:
    The values used here are simulation parameters
    for software testing only. They are NOT clinical
    thresholds.
    """

    def __init__(self):
        self.previous_skin_temperature = None
        self.previous_state = "NORMAL"

    def process(self, record):

        # -------------------------------------------------
        # 1. Read incoming data
        # -------------------------------------------------

        incubator_id = record["incubator_id"]

        skin_temperature = self._to_float(
            record["skin_temperature_c"]
        )

        air_temperature = self._to_float(
            record["air_temperature_c"]
        )

        dislodgement_flag = record["dislodgement_flag"] == "1"

        sensor_status = record["sensor_status"]

        signal_quality = record["signal_quality"]

        event = record["event"]

        # -------------------------------------------------
        # 2. Validate the data
        # -------------------------------------------------

        if skin_temperature is None:

            return self._result(
                record,
                state="SENSOR_ERROR",
                message="Skin temperature data unavailable."
            )

        if air_temperature is None:

            return self._result(
                record,
                state="SENSOR_ERROR",
                message="Incubator air temperature unavailable."
            )

        # -------------------------------------------------
        # 3. Calculate temperature difference
        # -------------------------------------------------

        temperature_difference = (
            skin_temperature - air_temperature
        )

        # -------------------------------------------------
        # 4. Calculate rate of change
        # -------------------------------------------------

        rate_of_change = 0.0

        if self.previous_skin_temperature is not None:

            rate_of_change = (
                skin_temperature
                - self.previous_skin_temperature
            )

        self.previous_skin_temperature = skin_temperature

        # -------------------------------------------------
        # 5. Sensor error
        # -------------------------------------------------

        if sensor_status == "ERROR":

            state = "SENSOR_ERROR"

            message = "Sensor data error detected."

        # -------------------------------------------------
        # 6. Dislodgement detection
        # -------------------------------------------------

        elif dislodgement_flag or sensor_status == "DISLODGED":

            state = "CRITICAL"

            message = (
                "SKIN TEMPERATURE PROBE DISLODGEMENT "
                "DETECTED."
            )

        # -------------------------------------------------
        # 7. Recovery
        # -------------------------------------------------

        elif event == "RECOVERING":

            state = "RECOVERING"

            message = (
                "Sensor connection restored. "
                "Monitoring recovery."
            )

        elif event == "RECOVERED":

            state = "RECOVERED"

            message = (
                "Sensor recovered. "
                "Telemetry returning to normal."
            )

        # -------------------------------------------------
        # 8. Signal quality problem
        # -------------------------------------------------

        elif signal_quality == "LOST":

            state = "SENSOR_ERROR"

            message = "Sensor signal lost."

        elif signal_quality == "POOR":

            state = "WARNING"

            message = "Poor sensor signal quality."

        # -------------------------------------------------
        # 9. Temperature variation
        # -------------------------------------------------

        elif event in (
            "TEMPERATURE_CHANGE",
            "TEMPERATURE_VARIATION"
        ):

            state = "WARNING"

            message = (
                "Significant temperature variation "
                "detected."
            )

        # -------------------------------------------------
        # 10. Normal state
        # -------------------------------------------------

        else:

            state = "NORMAL"

            message = "Telemetry operating normally."

        self.previous_state = state

        # -------------------------------------------------
        # 11. Return processed result
        # -------------------------------------------------

        return self._result(
            record,
            state=state,
            message=message,
            temperature_difference=temperature_difference,
            rate_of_change=rate_of_change
        )

    # -----------------------------------------------------
    # Convert value safely to float
    # -----------------------------------------------------

    @staticmethod
    def _to_float(value):

        try:

            if value is None or value == "":
                return None

            return float(value)

        except (ValueError, TypeError):

            return None

    # -----------------------------------------------------
    # Create standard detection result
    # -----------------------------------------------------

    @staticmethod
    def _result(
        record,
        state,
        message,
        temperature_difference=None,
        rate_of_change=None
    ):

        return {
            "timestamp": record["timestamp"],
            "incubator_id": record["incubator_id"],

            "skin_temperature_c":
                record["skin_temperature_c"],

            "air_temperature_c":
                record["air_temperature_c"],

            "sensor_status":
                record["sensor_status"],

            "signal_quality":
                record["signal_quality"],

            "dislodgement_flag":
                record["dislodgement_flag"],

            "event":
                record["event"],

            "state":
                state,

            "message":
                message,

            "temperature_difference_c":
                round(temperature_difference, 2)
                if temperature_difference is not None
                else None,

            "rate_of_change_c":
                round(rate_of_change, 2)
                if rate_of_change is not None
                else None
        }