export class Ctx {
	constructor(parent = null) {
		this._cancelled = false;
		this._waiters = [];
		this._children = new Set();

		if (parent instanceof Ctx) {
			parent._children.add(this);
			parent.wait().then(() => this.cancel());
		}
	}

	cancel() {
		if (this._cancelled) return;

		this._cancelled = true;

		// Cancel all children
		for (const child of this._children) {
			child.cancel();
		}
		this._children.clear();

		// Notify waiters
		for (const resolve of this._waiters) {
			resolve();
		}
		this._waiters = [];
	}

	cancelled() {
		return this._cancelled;
	}

	wait() {
		if (this._cancelled) return Promise.resolve();
		return new Promise(resolve => this._waiters.push(resolve));
	}

	static withCancel(parent = null) {
		return new Ctx(parent);
	}
}
