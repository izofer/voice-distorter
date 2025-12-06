let mediaRecorder;
let audioChunks = [];
let audioContext;
let analyser;
let dataArray;
let canvas, ctx;
let animationId;
let currentFilename = null;

const recordBtn = document.getElementById('recordBtn');
const statusText = document.getElementById('status');
const controlsSection = document.getElementById('controlsSection');
const visualizerContainer = document.querySelector('.visualizer-container');
const audioPlayback = document.getElementById('audioPlayback');
const effectBtns = document.querySelectorAll('.effect-btn');
const processingIndicator = document.getElementById('processingIndicator');
const resultSection = document.getElementById('resultSection');
const resultPlayback = document.getElementById('resultPlayback');
const downloadLink = document.getElementById('downloadLink');
const resetBtn = document.getElementById('resetBtn');
const cancelBtn = document.getElementById('cancelBtn');

// Initialize Canvas
canvas = document.getElementById('visualizer');
ctx = canvas.getContext('2d');
canvas.width = visualizerContainer.offsetWidth;
canvas.height = visualizerContainer.offsetHeight;

// Remove old Process Button if exists to avoid duplicates during dev reload
const oldBtn = document.querySelector('.transform-btn');
if (oldBtn) oldBtn.remove();

// Create Process Button
const processBtn = document.createElement('button');
processBtn.innerHTML = '<i class="fas fa-magic"></i> TRANSFORM';
processBtn.className = 'download-btn transform-btn';
processBtn.style.background = '#fff';
processBtn.style.color = '#000';
processBtn.style.marginTop = '20px';
processBtn.style.width = '100%';
document.querySelector('.effects-container').after(processBtn);

// Custom Controls Logic
const customControls = document.getElementById('customControls');
const pitchRange = document.getElementById('pitchRange');
const speedRange = document.getElementById('speedRange');
const distRange = document.getElementById('distRange');
const pitchVal = document.getElementById('pitchVal');
const speedVal = document.getElementById('speedVal');
const distVal = document.getElementById('distVal');

if (pitchRange) {
    pitchRange.oninput = () => pitchVal.innerText = pitchRange.value;
    speedRange.oninput = () => speedVal.innerText = speedRange.value;
    distRange.oninput = () => distVal.innerText = distRange.value;
}

// Event Listeners
recordBtn.addEventListener('click', toggleRecording);
resetBtn.addEventListener('click', resetApp);
if (cancelBtn) cancelBtn.addEventListener('click', resetApp);

effectBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        btn.classList.toggle('active');
        checkCustomVisibility();
    });
});

function checkCustomVisibility() {
    const activeBtns = Array.from(document.querySelectorAll('.effect-btn.active'));
    const isCustom = activeBtns.some(btn => btn.dataset.effect === 'Custom');
    if (customControls) {
        if (isCustom) {
            customControls.classList.remove('hidden');
        } else {
            customControls.classList.add('hidden');
        }
    }
}

processBtn.addEventListener('click', () => {
    const selectedEffects = Array.from(document.querySelectorAll('.effect-btn.active'))
        .map(btn => btn.dataset.effect);

    if (selectedEffects.length === 0) {
        alert("Please select at least one effect.");
        return;
    }

    const params = {
        pitch: pitchRange ? pitchRange.value : 1.0,
        speed: speedRange ? speedRange.value : 1.0,
        distortion: distRange ? distRange.value : 0
    };

    applyEffects(selectedEffects, params);
});


async function toggleRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        stopRecording();
    } else {
        startRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        // Audio Context for Visualizer
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        dataArray = new Uint8Array(analyser.frequencyBinCount);

        visualize();

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = uploadAudio;

        mediaRecorder.start();
        recordBtn.classList.add('recording');
        recordBtn.innerHTML = '<i class="fas fa-stop"></i>';
        statusText.innerText = "Recording... (Click to stop)";
    } catch (err) {
        console.error("Error accessing microphone", err);
        alert("Could not access microphone.");
    }
}

function stopRecording() {
    mediaRecorder.stop();
    recordBtn.classList.remove('recording');
    recordBtn.innerHTML = '<i class="fas fa-microphone"></i>';
    statusText.innerText = "Processing...";
    cancelAnimationFrame(animationId);
    if (audioContext) audioContext.close();
}

function visualize() {
    animationId = requestAnimationFrame(visualize);
    analyser.getByteFrequencyData(dataArray);

    ctx.fillStyle = '#050505'; // Background match
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const barWidth = (canvas.width / dataArray.length) * 2.5;
    let barHeight;
    let x = 0;

    for (let i = 0; i < dataArray.length; i++) {
        barHeight = dataArray[i] / 2;
        ctx.fillStyle = `rgb(${barHeight + 100}, 0, 50)`; // Red gradient
        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 1;
    }
}

async function uploadAudio() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('audio_data', audioBlob);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.filename) {
            currentFilename = data.filename;
            showControls();

            // Set playback preview
            const audioUrl = URL.createObjectURL(audioBlob);
            audioPlayback.src = audioUrl;
        }
    } catch (err) {
        console.error("Upload failed", err);
    }
}

function showControls() {
    controlsSection.classList.remove('hidden');
    recordBtn.parentElement.classList.add('hidden'); // Hide recorder
}

async function applyEffects(effectTypes, params) {
    if (!currentFilename) return;

    processingIndicator.classList.remove('hidden');
    resultSection.classList.add('hidden');

    try {
        const response = await fetch('/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: currentFilename,
                effects: effectTypes,
                params: params
            })
        });
        const data = await response.json();

        if (data.output_filename) {
            showResult(data.output_filename);
        } else {
            alert('Processing error: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        console.error("Effect failed", err);
    } finally {
        processingIndicator.classList.add('hidden');
    }
}

function showResult(filename) {
    resultSection.classList.remove('hidden');
    resultPlayback.src = `/download/${filename}`;
    downloadLink.href = `/download/${filename}`;
}

function resetApp() {
    location.reload();
}
