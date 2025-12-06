class AudioClient {
    constructor() {
        this.socket = null;
        this.mediaRecorder = null;
        this.isRecording = false;
        
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.transcriptDiv = document.getElementById('transcript');
        this.objectionsDiv = document.getElementById('objections');

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.connectWebSocket();
            
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            
            // Whisper expects 16kHz audio
            const targetSampleRate = 16000;
            
            // Use ScriptProcessor (deprecated but widely supported) for raw audio access
            // Buffer size 4096 provides ~0.25s latency at 16kHz, or ~0.09s at 48kHz
            const bufferSize = 4096; 
            this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
            
            source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            
            this.processor.onaudioprocess = (e) => {
                if (!this.isRecording || !this.socket || this.socket.readyState !== WebSocket.OPEN) return;

                const inputData = e.inputBuffer.getChannelData(0);
                
                // Resample to 16kHz if necessary
                let outputData = inputData;
                if (this.audioContext.sampleRate !== targetSampleRate) {
                    outputData = this.resample(inputData, this.audioContext.sampleRate, targetSampleRate);
                }
                
                // Convert to Float32 bytes (WhisperLive expects raw float32)
                // We create a copy to ensure we aren't sending shared memory
                const float32Data = new Float32Array(outputData);
                this.socket.send(float32Data.buffer);
            };

            this.isRecording = true;
            this.updateUI(true);
            
        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Could not access microphone. Please ensure you have granted permission.");
        }
    }

    // Simple linear interpolation resampler
    resample(data, oldSampleRate, newSampleRate) {
        if (oldSampleRate === newSampleRate) return data;
        
        const ratio = oldSampleRate / newSampleRate;
        const newLength = Math.round(data.length / ratio);
        const result = new Float32Array(newLength);
        
        for (let i = 0; i < newLength; i++) {
            const position = i * ratio;
            const index = Math.floor(position);
            const fraction = position - index;
            
            if (index + 1 < data.length) {
                result[i] = data[index] * (1 - fraction) + data[index + 1] * fraction;
            } else {
                result[i] = data[index];
            }
        }
        
        return result;
    }

    stopRecording() {
        if (this.isRecording) {
            if (this.processor) {
                this.processor.disconnect();
                this.processor = null;
            }
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }
            
            this.isRecording = false;
            this.updateUI(false);
            this.transcriptDiv.innerHTML += '<p class="text-red-500 italic text-sm mt-2">Stopped listening.</p>';
            
            if (this.socket) {
                this.socket.close();
            }
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/audio`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log("WebSocket connected");
            this.transcriptDiv.innerHTML = '<p class="text-green-500 italic">Connected! Listening...</p>';
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Received:", data);
            
            if (data.type === 'transcript') {
                this.handleTranscript(data);
            } else if (data.type === 'objection') {
                this.handleObjection(data);
            }
        };
        
        this.socket.onclose = () => {
            console.log("WebSocket disconnected");
        };
    }

    handleTranscript(data) {
        // Use start time as a unique ID for the segment
        // We round to 1 decimal place to avoid floating point issues
        const segmentId = `segment-${Math.round(data.start * 10)}`;
        let p = document.getElementById(segmentId);

        if (!p) {
            p = document.createElement('p');
            p.id = segmentId;
            p.classList.add('text-gray-500', 'transition-colors', 'duration-200');
            this.transcriptDiv.appendChild(p);
        }

        p.textContent = data.text;

        // If it looks like a complete sentence, darken it
        // We don't rely solely on is_final because it can be flaky
        if (data.is_final || /[.!?]$/.test(data.text)) {
            p.classList.remove('text-gray-500');
            p.classList.add('text-gray-800');
        }
        
        this.transcriptDiv.scrollTop = this.transcriptDiv.scrollHeight;
    }

    handleObjection(data) {
        const div = document.createElement('div');
        div.className = 'bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4 objection-alert';
        div.innerHTML = `
            <p class="font-bold">Objection Detected!</p>
            <p class="italic">"${data.text}"</p>
            <div class="mt-2 bg-white p-2 rounded border border-red-200">
                <p class="font-semibold text-sm text-gray-600">Suggested Response:</p>
                <p>${data.response}</p>
            </div>
        `;
        this.objectionsDiv.prepend(div);
    }

    updateUI(isRecording) {
        if (isRecording) {
            this.startBtn.classList.add('hidden');
            this.stopBtn.classList.remove('hidden');
        } else {
            this.startBtn.classList.remove('hidden');
            this.stopBtn.classList.add('hidden');
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new AudioClient();
});
