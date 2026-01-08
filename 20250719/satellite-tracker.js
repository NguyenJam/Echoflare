
import { Trigger } from './trigger.js?v=20250719';
import { Timer } from './timer.js?v=20250719';

export class SatelliteTracker {
	constructor(statusUrl) {
		this.statusUrl = statusUrl;
		this.satelliteId = '';
		this.subscribers = new Set();
		this.trigger = new Trigger();
	}

	setSatellite(id) {
		this.satelliteId = id ?? '';
		this.trigger.trigger();
	}

	onData(callback) {
		this.subscribers.add(callback);
		return () => {
			this.subscribers.delete(callback);
		}
	}

	async run(ctx) {
		const timer = new Timer(1000);
		try {

			while (!ctx.cancelled()) {
				if (this.satelliteId !== '') {
					try {

						const res = await fetch(`${this.statusUrl}/${this.satelliteId}`);
						if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
						const data = await res.json();

						for (const cb of this.subscribers) {
							try {
								cb(data);
							} catch (e) {
								console.error("Callback error:", e);
							}
						}
					} catch (err) {
						console.error("SatelliteTracker fetch failed:", err);
					}
				}

				await Promise.race([
					ctx.wait(),
					timer.wait(),
					this.trigger.wait(),
				]);

			}
		} finally {
			timer.stop();
		}
	}
}
