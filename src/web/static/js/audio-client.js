class AudioClient {
    constructor() {
        this.socket = null;
        this.mediaRecorder = null;
        this.isRecording = false;
        
        // Controls
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.connectionStatus = document.getElementById('connectionStatus');
        
        // UI Panels
        this.transcriptDiv = document.getElementById('transcript');
        this.scriptLocationDiv = document.getElementById('scriptLocation');
        this.keyPointsList = document.getElementById('keyPointsList');
        this.suggestionBox = document.getElementById('suggestionBox');

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
            
            // Load the AudioWorklet processor
            try {
                await this.audioContext.audioWorklet.addModule('/static/js/audio-processor.js');
            } catch (e) {
                console.error("Failed to load audio processor:", e);
                throw e;
            }
            
            const source = this.audioContext.createMediaStreamSource(stream);
            this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-processor');
            
            // Handle messages from the processor (audio data)
            this.workletNode.port.onmessage = (event) => {
                if (!this.isRecording || !this.socket || this.socket.readyState !== WebSocket.OPEN) return;
                
                const float32Data = event.data;
                this.socket.send(float32Data.buffer);
            };
            
            source.connect(this.workletNode);
            
            // Connect to destination via a muted gain node to keep the graph alive
            const gainNode = this.audioContext.createGain();
            gainNode.gain.value = 0;
            this.workletNode.connect(gainNode);
            gainNode.connect(this.audioContext.destination);

            this.isRecording = true;
            this.updateUI(true);
            
        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Could not access microphone. Please ensure you have granted permission.");
        }
    }

    stopRecording() {
        if (this.isRecording) {
            if (this.workletNode) {
                this.workletNode.disconnect();
                this.workletNode = null;
            }
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }
            
            this.isRecording = false;
            this.updateUI(false);
            this.transcriptDiv.innerHTML += '<p style="color: var(--status-price); font-style: italic; margin-top: 0.5rem;">Stopped listening.</p>';
            
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
            this.connectionStatus.textContent = "Connected";
            this.connectionStatus.style.color = "var(--status-success)";
            this.transcriptDiv.innerHTML = '<p style="color: var(--status-success); font-style: italic;">Connected! Listening...</p>';
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Received WebSocket message:", data);
            
            if (data.type === 'transcript') {
                this.handleTranscript(data);
            } else if (data.type === 'analysis') {
                console.log("Handling analysis data:", data);
                this.handleAnalysis(data);
            } else if (data.type === 'error') {
                console.error("Server Error:", data.error);
            }
        };
        
        this.socket.onclose = () => {
            console.log("WebSocket disconnected");
            this.connectionStatus.textContent = "Disconnected";
            this.connectionStatus.style.color = "var(--text-muted)";
        };
    }

    handleAnalysis(data) {
        // Update Script Location
        if (data.script_location) {
            this.scriptLocationDiv.textContent = data.script_location;
        }

        // Update Key Points
        if (data.key_points && Array.isArray(data.key_points)) {
            this.keyPointsList.innerHTML = data.key_points.map(point => `<li>${point}</li>`).join('');
        }

        // Update Suggestion
        if (data.suggestion) {
            this.suggestionBox.textContent = data.suggestion;
            // Add a subtle flash effect to indicate update
            this.suggestionBox.style.backgroundColor = "var(--bg-highlight)";
            setTimeout(() => {
                this.suggestionBox.style.backgroundColor = "";
            }, 200);
        }
    }

    handleTranscript(data) {
        // Use start time as a unique ID for the segment
        const segmentId = `segment-${Math.round(data.start * 10)}`;
        let p = document.getElementById(segmentId);

        if (!p) {
            p = document.createElement('div');
            p.id = segmentId;
            p.classList.add('transcript-line');
            this.transcriptDiv.appendChild(p);
        }

        p.textContent = data.text;

        // If it looks like a complete sentence, darken it
        if (data.is_final || /[.!?]$/.test(data.text)) {
            p.style.color = 'var(--text-primary)';
        }
        
        this.transcriptDiv.scrollTop = this.transcriptDiv.scrollHeight;
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
