
export class Radio {
    constructor(endpoint) {
        this.audio = null;
        this.satelliteId = null;
        this.endpoint =endpoint;
        this._state="off";
        this._onStatusChange = null;
    }

    async setSatellite(satelliteId) {
        if (this.satelliteId === satelliteId) {
            return;
        } else if (this.audio != null) {
            await this.powerOff();
            this.satelliteId = satelliteId
            this.powerOn();
        } else {
            this.satelliteId = satelliteId
        }
    }

    powerOn() {
        if (this.audio != null || this.satelliteId == null) {
            return;
        }

        this.audio = new Audio(`${this.endpoint}/${this.satelliteId}`)

        // Events that may indicate state changes
        this.audio.addEventListener('play', () => this.updateState());
        this.audio.addEventListener('playing', () => this.updateState());
        this.audio.addEventListener('pause', () => this.updateState());
        this.audio.addEventListener('waiting', () => this.updateState());
        this.audio.addEventListener('stalled',() => this.updateState());
        this.audio.addEventListener('canplay', () => this.updateState());
        this.audio.addEventListener('canplaythrough', () => this.updateState());
        this.audio.addEventListener('ended', () => this.updateState());
        this.audio.addEventListener('error', () => this.updateState());

        // Start playback
        this.audio.play().catch(err => {
            this.updateState();
            this.audio = null;
        });
    }

    async transmit(file) {
        if (!file) {
            return;
        }
        if (!file.name.endsWith('.wav')) {
            alert('Please select a .wav file.');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${this.endpoint}/${this.satelliteId}`, {
                method: 'POST',
                body: formData
            });

            const text = await response.text();

            if (response.ok) {
                alert(text);
            } else {
                alert(`${response.statusText}; ${text}`);
            }
        } catch (err) {
            console.error(err);
            alert('An error occurred during upload.');
        }
    }

    async powerOff() {
        if (this.audio != null) {
            this.audio.pause();
            this.audio=null;
        }
        return;
    }


    updateState() {
        if (this.audio == null || this.audio.paused) {
            this.audio = null;
            this._state = 'off';
        } else if (this.audio.readyState < 3) {
            this._state = 'buffering';
        } else {
            this._state = 'play';
        }

        if (this._onStatusChange != null) {
            this._onStatusChange(this._state);
        }
    };

        
    get onStatusChange() {
        return this._onStatusChange;
      }
    
    set onStatusChange(fn) {
        this._onStatusChange = fn;
    }

}