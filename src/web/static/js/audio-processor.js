class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.targetSampleRate = 16000;
        // Buffer size 4096 to match previous ScriptProcessor behavior
        this.bufferSize = 4096; 
        this._buffer = new Float32Array(this.bufferSize);
        this._bytesWritten = 0;
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input && input.length > 0) {
            const inputData = input[0];
            
            // Accumulate input data
            for (let i = 0; i < inputData.length; i++) {
                this._buffer[this._bytesWritten++] = inputData[i];
                
                if (this._bytesWritten >= this.bufferSize) {
                    this.flush();
                }
            }
        }
        return true; // Keep processor alive
    }

    flush() {
        const data = this._buffer.slice(0, this._bytesWritten);
        
        // Resample if necessary
        // sampleRate is a global variable in AudioWorkletScope
        let outputData = data;
        if (sampleRate !== this.targetSampleRate) {
            outputData = this.resample(data, sampleRate, this.targetSampleRate);
        }

        // Send to main thread
        this.port.postMessage(outputData, [outputData.buffer]);
        
        this._bytesWritten = 0;
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
}

registerProcessor('audio-processor', AudioProcessor);
