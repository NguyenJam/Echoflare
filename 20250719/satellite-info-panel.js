import { UpcomingPassesDialog } from './upcoming-passes-dialog.js?v=20250719';


export class SatelliteInfoPanel {
  constructor(container) {
    if (container == null) {
      throw new Error('Container element is required for SatelliteInfoPanel');
    }

    this.container = container;

    this._data = {
      name: '-',
      velocity: 0,
      slantRange: 0,
      alt_km: 0,
      doppler: 0,
      azimuth_deg: 0,
      elevation_deg: 0,
      upcoming_passes: [],
    };

    this._render();
  }

  _render() {

    this.panel = document.createElement('div');
    this.panel.style.position = 'absolute';
    this.panel.style.top = '4rem';
    this.panel.style.left = '1rem';
    this.panel.style.background = 'rgba(0, 0, 0, 0.4)';
    this.panel.style.color = '#fff';
    this.panel.style.padding = '1rem 1.5rem';
    this.panel.style.borderRadius = '1rem';
    this.panel.style.fontFamily = 'sans-serif';
    this.panel.style.fontSize = '0.95rem';
    this.panel.style.backdropFilter = 'blur(6px)';
    this.panel.style.webkitBackdropFilter = 'blur(6px)';
    this.panel.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)';
    this.panel.style.minWidth = '230px';
    this.panel.style.cursor = 'grab';
    this.panel.style.userSelect = 'none';
    this.panel.style.display = 'flex';
    this.panel.style.flexDirection = 'column';
    this.panel.style.gap = '1rem';

    const createTitle = (text) => {
      const el = document.createElement('div');
      el.textContent = text;
      el.style.fontWeight = 'bold';
      el.style.fontSize = '1.1rem';
      el.style.color = '#00ffff';
      el.style.marginBottom = '0.6rem';
      el.style.textTransform = 'uppercase';
      return el;
    };

    const createRow = (label) => {
      const row = document.createElement('div');
      row.style.display = 'flex';
      row.style.justifyContent = 'space-between';
      row.style.borderBottom = '1px solid rgba(255, 255, 255, 0.08)';

      const labelSpan = document.createElement('span');
      labelSpan.textContent = label;

      const valueSpan = document.createElement('span');

      row.appendChild(labelSpan);
      row.appendChild(valueSpan);
      this.panel.appendChild(row);

      return valueSpan;
    };

    // Title
    const title = createTitle('SATELLITE');
    this.panel.appendChild(title);
    this._satNameEl = title;

    // Rows with value references stored in class
    this._azimuthEl = createRow('Azimuth');
    this._elevationEl = createRow('Elevation');
    this._slantRangeEl = createRow('Slant range');
    this._altEl = createRow('Altitude');
    this._footprintEl = createRow('Footprint');
    this._velEl = createRow('Velocity');
    this._downlinkEl = createRow('Downlink');
    this._dopplerEl = createRow('Doppler');

    const showButton = document.createElement('sl-button');
    showButton.variant = 'default';
    showButton.size = 'small';
    showButton.innerText = 'Show Passes';

    const upcomingPassesDialog = new UpcomingPassesDialog(this.container);
    showButton.addEventListener('click', async () => {
      upcomingPassesDialog.show(this._data.upcoming_passes)
    });

    this.panel.appendChild(showButton);


    this._enableDrag(this.panel);
    this.container.appendChild(this.panel);


  }

  update(data) {
    this._data = { ...this._data, ...data };

    this._satNameEl.textContent = this._data.name;
    this._velEl.textContent = `${this._data.velocity_kms.toFixed(2)} km/s`;
    this._slantRangeEl.textContent = `${this._data.slant_range_km.toFixed(2)} km`;
    this._altEl.textContent = `${this._data.alt_km.toFixed(2)} km`;
    this._footprintEl.textContent = `${(2 * this._data.footprint_km).toFixed(2)} km`;
    this._downlinkEl.textContent = `${this._data.downlink_mhz.toFixed(3)} MHz`;
    this._dopplerEl.textContent = `${this._data.doppler_hz.toFixed(2)} Hz`;
    this._azimuthEl.textContent = `${this._data.azimuth_deg.toFixed(2)}°`;
    this._elevationEl.textContent = `${this._data.elevation_deg.toFixed(2)}°`;

  }


  _enableDrag(element) {
    let offsetX = 0, offsetY = 0, isDragging = false;

    const onMouseDown = (e) => {
      isDragging = true;
      offsetX = e.clientX - element.offsetLeft;
      offsetY = e.clientY - element.offsetTop;
      element.style.cursor = 'grabbing';
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    };

    const onMouseMove = (e) => {
      if (!isDragging) return;

      const maxLeft = window.innerWidth - element.offsetWidth;
      const maxTop = window.innerHeight - element.offsetHeight;

      let newLeft = e.clientX - offsetX;
      let newTop = e.clientY - offsetY;

      // Constrain to edges
      newLeft = Math.max(0, Math.min(newLeft, maxLeft));
      newTop = Math.max(0, Math.min(newTop, maxTop));

      element.style.left = `${newLeft}px`;
      element.style.top = `${newTop}px`;
    };

    const onMouseUp = () => {
      isDragging = false;
      element.style.cursor = 'grab';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    element.addEventListener('mousedown', onMouseDown);

    // Touch support
    element.addEventListener('touchstart', (e) => {
      const touch = e.touches[0];
      isDragging = true;
      offsetX = touch.clientX - element.offsetLeft;
      offsetY = touch.clientY - element.offsetTop;
      document.addEventListener('touchmove', onTouchMove);
      document.addEventListener('touchend', onTouchEnd);
    });

    const onTouchMove = (e) => {
      if (!isDragging) return;
      const touch = e.touches[0];

      const maxLeft = window.innerWidth - element.offsetWidth;
      const maxTop = window.innerHeight - element.offsetHeight;

      let newLeft = touch.clientX - offsetX;
      let newTop = touch.clientY - offsetY;

      newLeft = Math.max(0, Math.min(newLeft, maxLeft));
      newTop = Math.max(0, Math.min(newTop, maxTop));

      element.style.left = `${newLeft}px`;
      element.style.top = `${newTop}px`;
    };

    const onTouchEnd = () => {
      isDragging = false;
      document.removeEventListener('touchmove', onTouchMove);
      document.removeEventListener('touchend', onTouchEnd);
    };
  }


}
