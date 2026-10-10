
/* =========================================================
   NEOCARE AUDIBLE ALARM SYSTEM
   - Five alarm combinations
   - Two beeps per new alarm
   - Complete spoken messages
   - Queue prevents announcements being interrupted
   - Duplicate readings do not repeat the same alarm
   ========================================================= */

let alarmAudioContext = null;

const activeAlarmStates = new Map();
const alarmQueue = [];

let alarmQueuePlaying = false;


// ---------------------------------------------------------
// SAFE NUMBER CONVERSION
// ---------------------------------------------------------

function alarmNumber(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}


// ---------------------------------------------------------
// INITIALIZE AUDIO
// Call this after a user clicks/taps the page.
// ---------------------------------------------------------

async function initializeAlarmAudio() {
    const AudioContextClass =
        window.AudioContext || window.webkitAudioContext;

    if (!AudioContextClass) {
        throw new Error("Web Audio is not supported by this browser.");
    }

    if (!alarmAudioContext) {
        alarmAudioContext = new AudioContextClass();
    }

    if (alarmAudioContext.state === "suspended") {
        await alarmAudioContext.resume();
    }
}

// Unlock audio through a real user interaction.
document.addEventListener(
    "pointerdown",
    () => {
        initializeAlarmAudio().catch(console.error);
    },
    { once: true }
);


// ---------------------------------------------------------
// PLAY ONE BEEP
// ---------------------------------------------------------

function playBeep(duration = 220) {
    return new Promise(async (resolve, reject) => {
        try {
            await initializeAlarmAudio();

            const oscillator = alarmAudioContext.createOscillator();
            const gain = alarmAudioContext.createGain();
            const start = alarmAudioContext.currentTime;
            const end = start + duration / 1000;

            oscillator.type = "square";
            oscillator.frequency.setValueAtTime(900, start);

            gain.gain.setValueAtTime(0.0001, start);
            gain.gain.exponentialRampToValueAtTime(0.25, start + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.0001, end);

            oscillator.connect(gain);
            gain.connect(alarmAudioContext.destination);

            oscillator.onended = () => {
                oscillator.disconnect();
                gain.disconnect();
                resolve();
            };

            oscillator.start(start);
            oscillator.stop(end);
        } catch (error) {
            reject(error);
        }
    });
}


// ---------------------------------------------------------
// TWO BEEPS, PLAYED SEQUENTIALLY
// ---------------------------------------------------------

async function playTwoBeeps() {
    await playBeep(220);
    await new Promise(resolve => setTimeout(resolve, 160));
    await playBeep(220);
}


// ---------------------------------------------------------
// DETERMINE ALARM TYPE FROM ACTUAL READINGS
// ---------------------------------------------------------

function getAlarmType(data) {
    const temperature = alarmNumber(
        data.baby_temperature_c ??
        data.skin_temperature_c
    );

    const frequency = alarmNumber(
        data.movement_frequency_hz ??
        data.movement_frequency ??
        data.body_movements ??
        data.movement
    );

    const lowTemperature =
        temperature !== null && temperature < 36.5;

    const highTemperature =
        temperature !== null && temperature > 37.5;

    const movementAlarm =
        frequency !== null &&
        (frequency < 10 || frequency > 20);

    // Check combined conditions FIRST.
    if (lowTemperature && movementAlarm) {
        return "LOW_TEMP_MOVEMENT";
    }

    if (highTemperature && movementAlarm) {
        return "HIGH_TEMP_MOVEMENT";
    }

    if (lowTemperature) {
        return "LOW_TEMP";
    }

    if (highTemperature) {
        return "HIGH_TEMP";
    }

    if (movementAlarm) {
        return "MOVEMENT";
    }

    return null;
}


// ---------------------------------------------------------
// BUILD THE COMPLETE SPOKEN MESSAGE
// ---------------------------------------------------------

function getAlarmMessage(incubatorId, alarmType) {
    const match = String(incubatorId).match(/\d+/);

    const number = match
        ? Number(match[0])
        : incubatorId;

    const prefix = `Incubator ${number}`;

    const messages = {
        MOVEMENT:
            `${prefix} movement alarm`,

        LOW_TEMP:
            `${prefix} low temperature alarm`,

        HIGH_TEMP:
            `${prefix} high temperature alarm`,

        LOW_TEMP_MOVEMENT:
            `${prefix} low temperature and movement alarm`,

        HIGH_TEMP_MOVEMENT:
            `${prefix} high temperature and movement alarm`
    };

    return messages[alarmType] || "";
}


// ---------------------------------------------------------
// SPEAK ONE MESSAGE
// Do NOT call speechSynthesis.cancel() here.
// ---------------------------------------------------------

function speakAlarm(message) {
    return new Promise(resolve => {
        if (!("speechSynthesis" in window) || !message) {
            console.error("Speech synthesis unavailable:", message);
            resolve();
            return;
        }

        const utterance = new SpeechSynthesisUtterance(message);

        utterance.rate = 0.85;
        utterance.pitch = 1;
        utterance.volume = 1;

        utterance.onend = () => resolve();

        utterance.onerror = event => {
            console.error("Speech error:", event.error, message);
            resolve();
        };

        // Speak the complete message; don't cancel earlier speech.
        window.speechSynthesis.speak(utterance);
    });
}


// ---------------------------------------------------------
// PROCESS THE QUEUE ONE ALARM AT A TIME
// ---------------------------------------------------------

async function processAlarmQueue() {
    if (alarmQueuePlaying) return;

    alarmQueuePlaying = true;

    try {
        while (alarmQueue.length > 0) {
            const alarm = alarmQueue.shift();

            console.log("Playing alarm:", alarm.message);

            try {
                await playTwoBeeps();
            } catch (error) {
                console.error("Beep playback failed:", error);
            }

            // Small pause between beeps and speech.
            await new Promise(resolve => setTimeout(resolve, 250));

            await speakAlarm(alarm.message);

            // Pause before the next queued alarm.
            await new Promise(resolve => setTimeout(resolve, 200));
        }
    } finally {
        alarmQueuePlaying = false;

        // Handle an alarm added as the queue was finishing.
        if (alarmQueue.length > 0) {
            processAlarmQueue();
        }
    }
}


// ---------------------------------------------------------
// MAIN FUNCTION: CALL FOR EACH TELEMETRY READING
// ---------------------------------------------------------

function triggerAlarm(data) {
    const incubatorId = data.incubator_id;

    if (!incubatorId) return;

    const alarmType = getAlarmType(data);
    const previousType = activeAlarmStates.get(incubatorId);

    // Alarm cleared: allow the same alarm to sound next time.
    if (!alarmType) {
        activeAlarmStates.delete(incubatorId);
        return;
    }

    // Same alarm still active: don't queue duplicate readings.
    if (previousType === alarmType) {
        return;
    }

    // Record this new alarm state.
    activeAlarmStates.set(incubatorId, alarmType);

    const message = getAlarmMessage(incubatorId, alarmType);

    if (!message) return;

    console.log("New alarm detected:", message);

    // Queue the complete message so another incubator
    // cannot interrupt this announcement.
    alarmQueue.push({
        incubatorId,
        alarmType,
        message
    });

    processAlarmQueue();
}
