from datetime import datetime


class DetectionEngine:
    """
    NeoCare Detection Engine

    Movement:
        movement = 1 -> Baby is moving
        movement = 0 -> Baby is not moving

    Movement alarm:
        Baby has NOT moved continuously for 1 hour.

    NOTE:
    This is a software simulation and is NOT a clinical threshold.
    """

    LOW_MOVEMENT_THRESHOLD = 2
    HIGH_MOVEMENT_THRESHOLD = 20

    NO_MOVEMENT_ALARM_SECONDS = 60 * 60   # 1 hour

    def __init__(self):

        # Previous temperature
        self.previous_skin_temperature = None

        # Previous state
        self.previous_state = "NORMAL"

        # Stores when continuous no-movement started
        # separately for every incubator
        self.no_movement_start = {}

        # Stores current movement alarm state
        self.movement_alarm_active = {}

    def process(self, record):

        # -------------------------------------------------
        # 1. Read incoming data
        # -------------------------------------------------

        incubator_id = record["incubator_id"]

        skin_temperature = self._to_float(
            record.get("skin_temperature_c")
        )

        body_movements = self._to_float(
            record.get("body_movements")
        )

        dislodgement_flag = (
            str(record.get("dislodgement_flag", "0")) == "1"
        )

        sensor_status = record.get(
            "sensor_status",
            "CONNECTED"
        )

        signal_quality = record.get(
            "signal_quality",
            "GOOD"
        )

        event = record.get(
            "event",
            "NORMAL"
        )

        # -------------------------------------------------
        # 2. Validate movement
        # -------------------------------------------------

        if body_movements is None:

            return self._result(
                record,
                state="SENSOR_ERROR",
                message="Body movement data unavailable.",
                movement=0,
                movement_alarm=0,
                no_movement_duration_seconds=0
            )

        # -------------------------------------------------
        # 3. Convert movement into 1 / 0
        #
        # 1 = baby moving
        # 0 = baby not moving
        # -------------------------------------------------

        movement = 1 if body_movements > 0 else 0

        # -------------------------------------------------
        # 4. Movement status
        # -------------------------------------------------

        if body_movements < self.LOW_MOVEMENT_THRESHOLD:

            movement_status = "LOW"

        elif body_movements > self.HIGH_MOVEMENT_THRESHOLD:

            movement_status = "HIGH"

        else:

            movement_status = "NORMAL"

        # -------------------------------------------------
        # 5. Get telemetry timestamp
        # -------------------------------------------------

        current_time = self._parse_timestamp(
            record.get("timestamp")
        )

        if current_time is None:

            current_time = datetime.now()

        # -------------------------------------------------
        # 6. ONE-HOUR NO-MOVEMENT DETECTION
        # -------------------------------------------------

        if movement == 0:

            # Start timer when no movement begins
            if incubator_id not in self.no_movement_start:

                self.no_movement_start[incubator_id] = current_time

            start_time = self.no_movement_start[incubator_id]

            duration = (
                current_time - start_time
            ).total_seconds()

            no_movement_duration_seconds = max(
                0,
                duration
            )

            # Alarm after 1 continuous hour
            if duration >= self.NO_MOVEMENT_ALARM_SECONDS:

                movement_alarm = 1

                self.movement_alarm_active[
                    incubator_id
                ] = True

            else:

                movement_alarm = 0

        else:

            # -------------------------------------------------
            # Baby moved again
            # Reset the one-hour timer
            # -------------------------------------------------

            self.no_movement_start.pop(
                incubator_id,
                None
            )

            self.movement_alarm_active[
                incubator_id
            ] = False

            no_movement_duration_seconds = 0

            movement_alarm = 0

        # -------------------------------------------------
        # 7. Temperature rate of change
        # -------------------------------------------------

        rate_of_change = 0.0

        if skin_temperature is not None:

            if self.previous_skin_temperature is not None:

                rate_of_change = (
                    skin_temperature
                    - self.previous_skin_temperature
                )

            self.previous_skin_temperature = (
                skin_temperature
            )

        # -------------------------------------------------
        # 8. Existing detection logic
        # -------------------------------------------------

        if sensor_status == "ERROR":

            state = "SENSOR_ERROR"

            message = (
                "Sensor data error detected."
            )

        elif (
            dislodgement_flag
            or sensor_status == "DISLODGED"
        ):

            state = "CRITICAL"

            message = (
                "SKIN TEMPERATURE PROBE "
                "DISLODGEMENT DETECTED."
            )

        elif movement_alarm == 1:

            state = "CRITICAL"

            message = (
                "No baby movement detected "
                "for 1 hour."
            )

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

        elif signal_quality == "LOST":

            state = "SENSOR_ERROR"

            message = (
                "Sensor signal lost."
            )

        elif signal_quality == "POOR":

            state = "WARNING"

            message = (
                "Poor sensor signal quality."
            )

        elif event in (
            "TEMPERATURE_CHANGE",
            "TEMPERATURE_VARIATION"
        ):

            state = "WARNING"

            message = (
                "Significant temperature "
                "variation detected."
            )

        elif movement_status == "LOW":

            state = "WARNING"

            message = (
                "Low body movement detected."
            )

        elif movement_status == "HIGH":

            state = "WARNING"

            message = (
                "Elevated body movement detected."
            )

        else:

            state = "NORMAL"

            message = (
                "Telemetry operating normally."
            )

        self.previous_state = state

        # -------------------------------------------------
        # 9. Return processed result
        # -------------------------------------------------

        return self._result(
            record=record,
            state=state,
            message=message,
            movement_status=movement_status,
            movement=movement,
            movement_alarm=movement_alarm,
            no_movement_duration_seconds=(
                no_movement_duration_seconds
            ),
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

        except (
            ValueError,
            TypeError
        ):

            return None

    # -----------------------------------------------------
    # Parse timestamp
    # -----------------------------------------------------

    @staticmethod
    def _parse_timestamp(value):

        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        try:

            text = str(value).strip()

            return datetime.fromisoformat(
                text.replace("Z", "+00:00")
            ).replace(tzinfo=None)

        except (
            ValueError,
            TypeError
        ):

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
        movement=0,
        movement_alarm=0,
        no_movement_duration_seconds=0,
        rate_of_change=None
    ):

        return {

            "baby_id":
                record.get("baby_id", ""),

            "baby_name":
                record.get("baby_name", ""),

            "timestamp":
                record.get("timestamp"),

            "incubator_id":
                record.get("incubator_id"),

            "skin_temperature_c":
                record.get("skin_temperature_c"),

            "baby_temperature_c":
                record.get("baby_temperature_c"),

            "body_movements":
                record.get("body_movements"),

            # -----------------------------------------
            # NEW MOVEMENT FIELDS
            # -----------------------------------------

            "movement":
                movement,

            "movement_status":
                movement_status,

            "movement_alarm":
                movement_alarm,

            "no_movement_duration_seconds":
                round(
                    no_movement_duration_seconds,
                    2
                ),

            "no_movement_duration_minutes":
                round(
                    no_movement_duration_seconds / 60,
                    2
                ),

            # -----------------------------------------
            # EXISTING SENSOR INFORMATION
            # -----------------------------------------

            "sensor_status":
                record.get(
                    "sensor_status"
                ),

            "signal_quality":
                record.get(
                    "signal_quality"
                ),

            "dislodgement_flag":
                record.get(
                    "dislodgement_flag"
                ),

            "event":
                record.get("event"),

            # -----------------------------------------
            # DETECTION RESULT
            # -----------------------------------------

            "state":
                state,

            "message":
                message,

            "rate_of_change_c":
                round(
                    rate_of_change,
                    2
                )
                if rate_of_change is not None
                else None,

            # -----------------------------------------
            # Keep existing dataset alarm fields
            # -----------------------------------------

            "temperature_alarm":
                int(
                    record.get(
                        "temperature_alarm",
                        0
                    ) or 0
                ),

            "overall_alarm":
                int(
                    record.get(
                        "overall_alarm",
                        0
                    ) or 0
                )
        }