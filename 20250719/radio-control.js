export class RadioControl {
    constructor(container) {
        this.root = document.createElement('div');
        container.appendChild(this.root);

        this._status = 'off';
        this._frequencyMhz = 437.625;
        this._onPowerChange = () => {};
        this._onTransmit = () => {};
        this._createUI();
        this._updateStatus();
        this._updateFrequency();
    }

    _createUI() {
        this.root.innerHTML = '';
        this.root.style.flex = '1';

        const container = document.createElement('div');
        container.style.display = 'flex';
        container.style.alignItems = 'center';
        container.style.gap = '0.75rem';

        // --- Button ---
        this.button = document.createElement('sl-button');
        this.button.setAttribute('id', 'toggleBtn');
        this.button.addEventListener('click', () => {
            this._onPowerChange(this._status === 'off');
        });

        // --- Frequency display ---
        this.freqDisplay = document.createElement('div');
        this.freqDisplay.id = 'frequencyDisplay';
        this.freqDisplay.style.fontFamily = `'DSEG14-Modern', monospace`;
        this.freqDisplay.style.fontSize = '1.6rem';
        this.freqDisplay.style.color = '#0ff';
        this.freqDisplay.style.letterSpacing = '0.12rem';
        this.freqDisplay.style.whiteSpace = 'nowrap';

      

        // --- Transmit button w/ tooltip ---
        this.transmitButton = document.createElement('sl-icon-button');
        this.transmitButton.style.color = "#fff";
        this.transmitButton.setAttribute('variant', 'primary');
        this.transmitButton.setAttribute('name', 'broadcast-pin');

        this.transmitButtonTooltip = document.createElement('sl-tooltip');
        this.transmitButtonTooltip.content = "Transmit .wav";
        this.transmitButtonTooltip.appendChild(this.transmitButton);

        // --- Hidden file input ---
        this.fileInput = document.createElement('input');
        this.fileInput.type = "file";
        this.fileInput.accept = ".wav";
        this.fileInput.style.display = "none";

        this.transmitButton.addEventListener('click', () => {
            this.fileInput.click();
        });

        this.fileInput.addEventListener('change', async () => {
            if (this.fileInput.files.length > 0) {
                const file = this.fileInput.files[0];
                this.fileInput.value = '';
                await this._onTransmit(file);
            }
        });

        container.appendChild(this.button);
        container.appendChild(this.freqDisplay);
        container.appendChild(this.transmitButtonTooltip);
        container.appendChild(this.fileInput);
        this.root.appendChild(container);
    }

    _updateStatus() {

        const icon = document.createElement('sl-icon');
        icon.setAttribute('name', 'power');

        const label = document.createElement('span');
        label.textContent = 'Radio';

        const content = document.createElement('span');
        content.style.display = 'inline-flex';
        content.style.alignItems = 'center';
        content.style.gap = '8px';
        content.appendChild(icon);
        content.appendChild(label);

        this.button.innerHTML = '';
        this.button.setAttribute('variant', this._status === 'off' ? 'neutral' : 'primary');
        this.button.appendChild(content);
    }

    _updateFrequency() {
        const totalHz = Math.round(this._frequencyMhz * 1_000_000);
        const mhz = Math.floor(totalHz / 1_000_000);
        const khz = Math.floor((totalHz % 1_000_000) / 1_000);
        const hz = totalHz % 1_000;

        let text =''
        if (this._status == 'off') {
            text = '888.888.888 FM';
            this.freqDisplay.style.color = '#666';
        } else if (this._status == 'buffering') {
            text ='BUF.FER.ING FM';
            this.freqDisplay.style.color = '#0ff';
        } else {
            this.freqDisplay.style.color = '#0ff';
            text = `${mhz}.${khz.toString().padStart(3, '0')}.${hz.toString().padStart(3, '0')} FM`;
        } 
        this.freqDisplay.textContent = text;

    }

    // --- Public API ---
    setStatus(status) {
        if (status !== this._status) {
            this._status = status;
            this._updateStatus();
            this._updateFrequency();
        }
    }

    setFrequency(freqMhz) {
        if (freqMhz !== this._frequencyMhz) {
            this._frequencyMhz = freqMhz;
            this._updateFrequency();
        }
    }

    get onPowerChange() {
        return this._onPowerChange;
    }

    set onPowerChange(fn) {
        this._onPowerChange = fn;
    }

    get onTransmit() {
        return this._onTransmit;
    }

    set onTransmit(fn) {
        this._onTransmit = fn;
    }


    
}
