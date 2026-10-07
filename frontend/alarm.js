/* =========================================================
   NeoCare Alarm System
   ---------------------------------------------------------
   Movement:
       < 10 Hz  -> Movement Alarm
       10-20 Hz -> Normal
       > 20 Hz  -> Movement Alarm

   Temperature:
       < 36.5°C -> Low Temperature Alarm
       36.5-37.5°C -> Normal
       > 37.5°C -> High Temperature Alarm

   Alarm:
       2 beeps + spoken alarm message
   ========================================================= */


let alarmAudioContext = null;


// ---------------------------------------------------------
// INITIALIZE AUDIO
// ---------------------------------------------------------

function initializeAlarmAudio() {

    if (!alarmAudioContext) {
        alarmAudioContext =
            new (window.AudioContext ||
                 window.webkitAudioContext)();
    }

    if (alarmAudioContext.state === "suspended") {
        alarmAudioContext.resume();
    }
}


// ---------------------------------------------------------
// CREATE ONE BEEP
// ---------------------------------------------------------

function playBeep(duration = 300) {

    initializeAlarmAudio();

    const oscillator =
        alarmAudioContext.createOscillator();

    const gain =
        alarmAudioContext.createGain();

    oscillator.type = "square";

    oscillator.frequency.setValueAtTime(
        1000,
        alarmAudioContext.currentTime
    );

    gain.gain.setValueAtTime(
        0.35,
        alarmAudioContext.currentTime
    );

    oscillator.connect(gain);
    gain.connect(alarmAudioContext.destination);

    oscillator.start();

    oscillator.stop(
        alarmAudioContext.currentTime +
        duration / 1000
    );
}


// ---------------------------------------------------------
// TWO BEEP ALARM
// ---------------------------------------------------------

function playTwoBeeps() {

    initializeAlarmAudio();

    // First beep
    playBeep(300);

    // Second beep
    setTimeout(() => {
        playBeep(300);
    }, 450);
}


// ---------------------------------------------------------
// GET INCUBATOR NUMBER
// ---------------------------------------------------------

function getIncubatorNumber(incubatorId) {

    if (!incubatorId) {
        return "Unknown";
    }

    const match =
        String(incubatorId).match(/\d+/);

    if (match) {
        return Number(match[0]);
    }

    return incubatorId;
}


// ---------------------------------------------------------
// DETERMINE ALARM TYPE
// ---------------------------------------------------------

function getAlarmType(data) {

    const temperature =
        Number(
            data.baby_temperature ??
            data.baby_temp ??
            data.temperature
        );

    const movementFrequency =
        Number(
            data.movement_frequency ??
            data.movement_frequency_hz ??
            data.movement_hz ??
            data.frequency
        );


    // -------------------------------
    // Temperature condition
    // -------------------------------

    const lowTemperature =
        Number.isFinite(temperature) &&
        temperature < 36.5;


    const highTemperature =
        Number.isFinite(temperature) &&
        temperature > 37.5;


    // -------------------------------
    // Movement condition
    // -------------------------------

    const movementAlarm =
        Number.isFinite(movementFrequency) &&
        (
            movementFrequency < 10 ||
            movementFrequency > 20
        );


    // -------------------------------
    // Determine combination
    // -------------------------------

    if (lowTemperature && movementAlarm) {

        return {
            active: true,
            type: "LOW_MOVEMENT",
            message: "low temperature and movement alarm"
        };
    }


    if (highTemperature && movementAlarm) {

        return {
            active: true,
            type: "HIGH_MOVEMENT",
            message: "high temperature and movement alarm"
        };
    }


    if (lowTemperature) {

        return {
            active: true,
            type: "LOW_TEMPERATURE",
            message: "low temperature alarm"
        };
    }


    if (highTemperature) {

        return {
            active: true,
            type: "HIGH_TEMPERATURE",
            message: "high temperature alarm"
        };
    }


    if (movementAlarm) {

        return {
            active: true,
            type: "MOVEMENT",
            message: "movement alarm"
        };
    }


    return {
        active: false,
        type: "NONE",
        message: ""
    };
}


// ---------------------------------------------------------
// SPEAK ALARM WORDING
// ---------------------------------------------------------

function speakAlarm(message) {

    if (!("speechSynthesis" in window)) {
        console.warn(
            "Speech synthesis is not supported."
        );

        return;
    }


    window.speechSynthesis.cancel();


    const speech =
        new SpeechSynthesisUtterance(message);

    speech.rate = 0.9;

    speech.pitch = 1;

    speech.volume = 1;


    window.speechSynthesis.speak(speech);
}


// ---------------------------------------------------------
// TRIGGER COMPLETE ALARM
// ---------------------------------------------------------

function triggerAlarm(data) {

    const incubatorNumber =
        getIncubatorNumber(
            data.incubator_id
        );


    const alarm =
        getAlarmType(data);


    if (!alarm.active) {
        return;
    }


    const spokenMessage =
        `Incubator ${incubatorNumber} ${alarm.message}`;


    console.log(
        "ALARM:",
        spokenMessage
    );


    // Two beeps
    playTwoBeeps();


    // Spoken wording
    setTimeout(() => {

        speakAlarm(
            spokenMessage
        );

    }, 900);
}


// ---------------------------------------------------------
// TEST ALARMS
// ---------------------------------------------------------

function testMovementAlarm() {

    triggerAlarm({
        incubator_id: "INC-001",
        baby_temperature: 37.0,
        movement_frequency: 25
    });
}


function testLowTemperatureAlarm() {

    triggerAlarm({
        incubator_id: "INC-001",
        baby_temperature: 35.8,
        movement_frequency: 15
    });
}


function testHighTemperatureAlarm() {

    triggerAlarm({
        incubator_id: "INC-001",
        baby_temperature: 38.2,
        movement_frequency: 15
    });
}


function testLowTemperatureMovementAlarm() {

    triggerAlarm({
        incubator_id: "INC-001",
        baby_temperature: 35.8,
        movement_frequency: 7
    });
}


function testHighTemperatureMovementAlarm() {

    triggerAlarm({
        incubator_id: "INC-001",
        baby_temperature: 38.2,
        movement_frequency: 25
    });
}