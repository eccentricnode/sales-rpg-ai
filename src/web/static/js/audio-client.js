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
            
            this.mediaRecorder = new MediaRecorder(stream);
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && this.socket && this.socket.readyState === WebSocket.OPEN) {
                    // Send audio blob to server
                    this.socket.send(event.data); 
                }
            };

            this.mediaRecorder.start(250); // Send chunks every 250ms
            this.isRecording = true;
            this.updateUI(true);
            
        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Could not access microphone. Please ensure you have granted permission.");
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            this.isRecording = false;
            this.updateUI(false);
            
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
        // Append transcript
        const p = document.createElement('p');
        p.textContent = data.text;
        if (data.is_final) {
            p.classList.add('text-gray-800');
        } else {
            p.classList.add('text-gray-500');
        }
        this.transcriptDiv.appendChild(p);
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
