export class UpcomingPassesDialog {
  constructor(container) {
    this.container = container;

    this.dialog = document.createElement('sl-dialog');
    this.dialog.label = 'Upcoming Passes';
    this.dialog.className = 'passes-dialog';
    this.dialog.style.setProperty('--width', '720px');

    this.dialog.innerHTML = `
      <div class="passes-glass">
        <table class="passes-table">
          <thead>
            <tr>
              <th>AOS</th>
              <th>EOS</th>
              <th>Duration</th>
              <th>Max Elevation</th>
            </tr>
          </thead>
          <tbody id="passesTableBody">
          </tbody>
        </table>
        <p>All times are displayed in your local timezone.</p>
      </div>
      <sl-button slot="footer" variant="primary" id="closePasses">Close</sl-button>
    `;

    this.container.appendChild(this.dialog);

    this.tableBody = this.dialog.querySelector('#passesTableBody');
    this.dialog.querySelector('#closePasses').addEventListener('click', () => this.dialog.hide());

    this._injectStyles();
  }

  show(passes) {
    this.tableBody.innerHTML = '';

    for (const pass of passes) {
      const row = document.createElement('tr');
      const startDate = new Date(pass.start)
      const endDate = new Date(pass.end)

      const timeFormat = {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }
      const duration = endDate.getTime() - startDate.getTime()
      row.innerHTML = `
        <td>${startDate.toLocaleDateString()} ${startDate.toLocaleTimeString(undefined, timeFormat)}</td>
        <td>${endDate.toLocaleDateString()} ${endDate.toLocaleTimeString(undefined, timeFormat)}</td>
        <td>${this.formatDuration(duration / 1000)}</td>
        <td>${pass.max_elevation.toFixed(1)}°</td>
      `;
      this.tableBody.appendChild(row);
    }

    this.dialog.show();
  }

  formatDuration(seconds) {
    const hrs = String(Math.floor(seconds / 3600)).padStart(2, '0');
    const mins = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
    const secs = String(seconds % 60).padStart(2, '0');
    return `${hrs}:${mins}:${secs}`;
  }

  _injectStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .passes-dialog::part(panel) {
        backdrop-filter: blur(12px);
        background: rgba(30, 30, 30, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        color: #e0e0e0;
        font-family: 'Segoe UI', sans-serif;
      }

      .passes-glass {
        max-height: 60vh;
        overflow-y: auto;
      }

      .passes-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.88rem;
        color: #eee;
      }

      .passes-table thead th {
        background-color: rgba(255, 255, 255, 0.1);
        position: sticky;
        top: 0;
        padding: 0.6em;
        text-align: left;
        font-weight: 600;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
      }

      .passes-table td {
        padding: 0.5em 0.75em;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      }

      .passes-table tr:hover {
        background-color: rgba(255, 255, 255, 0.05);
      }
    `;
    document.head.appendChild(style);
  }
}
