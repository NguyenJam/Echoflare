import { marked } from 'https://cdn.jsdelivr.net/npm/marked/+esm';

export class BriefingManager {
  constructor(container) {
    this.container = container;
    this._injectFonts();
    this._injectStyles();
    this._createUI();
  }

  async _createUI() {
    // --- Modal ---
    this.dialog = document.createElement('sl-dialog');
    this.dialog.className = 'briefing-modal';
    this.dialog.setAttribute('no-header', '');
    this.dialog.setAttribute('no-footer', '');
    this.dialog.style.setProperty('--width', '100vw');
    this.dialog.style.setProperty('--height', '100vh');
    this.dialog.style.padding = '0';

    this.dialog.innerHTML = `
      <div class="briefing-glass">
        <div id="briefingContent">Loading briefing...</div>
        <div style="margin-top: 2rem; text-align: center;">
          <sl-button variant="primary" size="large" id="ackBtn">Acknowledge & Enter Console</sl-button>
        </div>
      </div>
    `;

    this.container.appendChild(this.dialog);

    // --- Close button ---
    this.closeButton = document.createElement('sl-icon-button');
    this.closeButton.setAttribute('name', 'x');
    this.closeButton.setAttribute('label', 'Close briefing');
    this.closeButton.style.position = 'absolute';
    this.closeButton.style.top = '1rem';
    this.closeButton.style.right = '1rem';
    this.closeButton.style.zIndex = '10';
    this.closeButton.style.color = 'white';
    this.closeButton.style.fontSize = '1.25rem';

    this.closeButton.addEventListener('click', () => {
      this.dialog.hide();
    });

    this.dialog.appendChild(this.closeButton);

    // --- Top-right icon button ---
    this.iconButton = document.createElement('sl-icon-button');
    this.iconButton.setAttribute('name', 'journal-text');
    this.iconButton.setAttribute('label', 'Mission Briefing');
    this.iconButton.style.color = 'white';
    this.iconButton.style.fontSize = '1.5rem';
    this.container.appendChild(this.iconButton);

    this.iconButton.addEventListener('click', async () => {
      await this.showBriefing();
    });

    this.dialog.querySelector('#ackBtn').addEventListener('click', () => {
      this.dialog.hide();
      localStorage.setItem('briefingAcknowledged', 'true');
    });

    // --- Show on first visit ---
    await customElements.whenDefined('sl-dialog');

    if (!localStorage.getItem('briefingAcknowledged')) {
      await this.showBriefing();
    } else {
      this.iconButton.style.display = 'block';
    }
}

  async showBriefing() {
    if (!this._briefingLoaded) {
      await this._loadMarkdown();
      this._briefingLoaded = true;
    }
    this.dialog.show();
  }

  async _loadMarkdown() {
    try {
      const res = await fetch('resources/README.md');
      const markdown = await res.text();
      this.dialog.querySelector('#briefingContent').innerHTML = marked.parse(markdown);
    } catch (err) {
      this.dialog.querySelector('#briefingContent').innerHTML = '<p style="color: red;">Failed to load briefing.</p>';
      console.error(err);
    }
  }

  _injectFonts() {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Sans:wght@400;600&display=swap';
    document.head.appendChild(link);
  }

  _injectStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .briefing-modal::part(panel) {
        backdrop-filter: blur(16px);
        background: rgba(20, 20, 20, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        border-radius: 0;
        color: #e0e0e0;
      }

      .briefing-glass {
        padding: 3rem;
        max-width: 800px;
        margin: 0 auto;
        font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
        font-size: 16px;
        line-height: 1.75;
        letter-spacing: 0.1px;
        color: #e0e0e0;
      }

      .briefing-glass h1,
      .briefing-glass h2,
      .briefing-glass h3 {
        font-family: 'Bebas Neue', sans-serif;
        font-weight: 700;
        font-size: 1.75rem;
        line-height: 1.3;
        color: white;
        margin-bottom: 1rem;
      }

      .briefing-glass h1 {
        font-size: 3rem;
        letter-spacing: 0.03em;
        margin-bottom: 1.5rem;
        line-height: 1.1;
      }

      .briefing-glass ul {
        margin-left: 1.25em;
        list-style-type: disc;
      }

      .briefing-glass blockquote {
        font-style: italic;
        font-size: 1.05em;
        border-left: 3px solid rgba(255,255,255,0.25);
        padding-left: 1em;
        margin: 1.5em 0;
        color: #ccc;
        opacity: 0.9;
      }

      .briefing-glass pre {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1em;
        border-radius: 6px;
        overflow-x: auto;
        font-family: 'Fira Mono', 'Courier New', monospace;
        font-size: 0.9rem;
        line-height: 1.5;
        margin: 1.25em 0;
        color: #ddd;
      }

      .briefing-glass p {
        margin-bottom: 1.2em;
      }

      .briefing-glass a {
        color: #7db4d4;
        text-decoration: underline;
      }

      .briefing-glass a:hover {
        color: #a6d5f5;
      }

    .briefing-glass {
      scrollbar-width: thin;
      scrollbar-color: #666 transparent;
    }

    sl-dialog::part(body) {
        scrollbar-width: thin;
        scrollbar-color: #666 transparent;
        overscroll-behavior: contain;
    }

    /* WebKit (Chrome, Safari, Edge) */
    sl-dialog::part(body)::-webkit-scrollbar {
      width: 8px;
    }
    sl-dialog::part(body)::-webkit-scrollbar-track {
      background: transparent;
    }
    sl-dialog::part(body)::-webkit-scrollbar-thumb {
      background-color: #666;
      border-radius: 4px;
      border: 2px solid transparent;
      background-clip: content-box;
    }
    `;
    document.head.appendChild(style);
  }
}
