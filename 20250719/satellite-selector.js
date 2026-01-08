export class SatelliteSelector {
    constructor(container, endpointUrl) {
        this._onSatelliteSelected = () => { };
        this.endpointUrl = endpointUrl;
        this._satellites = [];
        this._selectedName = '';

        this.element = document.createElement('div');
        container.appendChild(this.element);

        this._render(); // Initial render (empty state)
        this._fetchAndSetSatellites(); // Later populates + re-renders
    }

    async _fetchAndSetSatellites() {
        try {
            const response = await fetch(this.endpointUrl);
            const satellites = await response.json();

            if (Array.isArray(satellites)) {
                this._satellites = satellites;
                this._selectedName = this._satellites[0];
                this._render();
                this._onSatelliteSelected(this._selectedName);
            }
        } catch (err) {
            console.error('Failed to fetch satellite list:', err);
        }
    }

    _render() {
        if (this._satellites.length < 2) {
            return ''
        }
        
        this.element.innerHTML = '';

        const container = document.createElement('div');
        container.style.display = 'flex';
        container.style.alignItems = 'center';
        container.style.gap = '0.75rem';

        const label = document.createElement('span');
        label.textContent = 'Satellite:';
        label.style.fontWeight = 'bold';
        label.style.color = '#0ff';

        this.select = document.createElement('sl-select');
        this.select.placeholder = 'Select satellite';
        this.select.style.minWidth = '200px';


        // Populate options if we have data
        for (const name of this._satellites) {
            const option = document.createElement('sl-option');
            option.value = encodeURIComponent(name);
            option.textContent = name;
            if (name === this._selectedName) {
                option.selected = true;
            }
            this.select.appendChild(option);
        }

        container.appendChild(label);
        container.appendChild(this.select);

        this.select.addEventListener('sl-change', () => {
            const selected = decodeURIComponent(this.select.value);
            if (selected && this._onSatelliteSelected) {
                this._onSatelliteSelected(selected);
            }
        });

        this.element.appendChild(container);
    }

    get onSatelliteSelected() {
        return this._onSatelliteSelected;
    }

    set onSatelliteSelected(fn) {
        this._onSatelliteSelected = fn;
    }
}
