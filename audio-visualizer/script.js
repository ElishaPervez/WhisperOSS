class AudioVisualizer {
    constructor() {
        this.visualizer = document.getElementById('visualizer');
        this.startBtn = document.getElementById('startBtn');
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.source = null;
        this.animationId = null;
        this.isActive = false;
        this.barCount = 12;

        this.init();
    }

    init() {
        // Create bars
        this.createBars();

        // Add click handler
        this.startBtn.addEventListener('click', () => this.toggle());

        // Start with idle animation
        this.setIdleState(true);
    }

    createBars() {
        this.visualizer.innerHTML = '';
        for (let i = 0; i < this.barCount; i++) {
            const bar = document.createElement('div');
            bar.className = 'bar';
            bar.style.height = '4px';
            this.visualizer.appendChild(bar);
        }
    }

    setIdleState(idle) {
        const bars = this.visualizer.querySelectorAll('.bar');
        bars.forEach(bar => {
            if (idle) {
                bar.classList.add('idle');
            } else {
                bar.classList.remove('idle');
            }
        });
    }

    async toggle() {
        if (this.isActive) {
            this.stop();
        } else {
            await this.start();
        }
    }

    async start() {
        try {
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false
                }
            });

            // Create audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();

            // Configure analyser
            this.analyser.fftSize = 64;
            this.analyser.smoothingTimeConstant = 0.8;

            // Connect source to analyser
            this.source = this.audioContext.createMediaStreamSource(stream);
            this.source.connect(this.analyser);

            // Create data array for frequency data
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);

            // Update UI
            this.isActive = true;
            this.startBtn.classList.add('active');
            this.setIdleState(false);

            // Start visualization
            this.animate();

        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please ensure microphone permissions are granted.');
        }
    }

    stop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }

        if (this.source) {
            this.source.disconnect();
            this.source = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.isActive = false;
        this.startBtn.classList.remove('active');

        // Reset bars and set to idle
        const bars = this.visualizer.querySelectorAll('.bar');
        bars.forEach(bar => {
            bar.style.height = '4px';
        });
        this.setIdleState(true);
    }

    animate() {
        if (!this.isActive) return;

        this.analyser.getByteFrequencyData(this.dataArray);

        const bars = this.visualizer.querySelectorAll('.bar');
        const step = Math.floor(this.dataArray.length / this.barCount);

        bars.forEach((bar, index) => {
            // Get frequency value for this bar
            const dataIndex = index * step;
            let value = this.dataArray[dataIndex] || 0;

            // Apply some smoothing and scaling
            // Boost lower frequencies slightly for better visual effect
            const boost = index < this.barCount / 2 ? 1.2 : 1;
            value = value * boost;

            // Map value (0-255) to height (4-30 pixels)
            const minHeight = 4;
            const maxHeight = 30;
            const height = minHeight + (value / 255) * (maxHeight - minHeight);

            bar.style.height = `${height}px`;
        });

        this.animationId = requestAnimationFrame(() => this.animate());
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new AudioVisualizer();
});
