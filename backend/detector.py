class DetectionEngine:
    """
    Processes telemetry data and determines the
    current monitoring state.

    NOTE:
    The values used here are simulation parameters
    for software testing only. They are NOT clinical
    thresholds.
    """

    # Simulation-only thresholds for body movement classification.
    # NOT clinical thresholds.
    LOW_MOVEMENT_THRESHOLD = 2
    HIGH_MOVEMENT_THRESHOLD = 20

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

        body_movements = self._to_float(
            record["body_movements"]
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

        if body_movements is None:

            return self._result(
                record,
                state="SENSOR_ERROR",
                message="Body movement data unavailable."
            )

        # -------------------------------------------------
        # 3. Classify body movement level
        # -------------------------------------------------

        if body_movements < self.LOW_MOVEMENT_THRESHOLD:
            movement_status = "LOW"

        elif body_movements > self.HIGH_MOVEMENT_THRESHOLD:
            movement_status = "HIGH"

        else:
            movement_status = "NORMAL"

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
        # 10. Body movement variation
        # -------------------------------------------------

        elif movement_status == "LOW":

            state = "WARNING"

            message = "Low body movement detected."

        elif movement_status == "HIGH":

            state = "WARNING"

            message = "Elevated body movement detected."

        # -------------------------------------------------
        # 11. Normal state
        # -------------------------------------------------

        else:

            state = "NORMAL"

            message = "Telemetry operating normally."

        self.previous_state = state

        # -------------------------------------------------
        # 12. Return processed result
        # -------------------------------------------------

        return self._result(
            record,
            state=state,
            message=message,
            movement_status=movement_status,
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
        movement_status=None,
        rate_of_change=None
    ):

        return {
            "timestamp": record["timestamp"],
            "incubator_id": record["incubator_id"],

            "skin_temperature_c":
                record["skin_temperature_c"],

            "body_movements":
                record["body_movements"],

            "movement_status":
                movement_status,

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

            "rate_of_change_c":
                round(rate_of_change, 2)
                if rate_of_change is not None
                else None
        }