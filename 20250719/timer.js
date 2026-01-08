import { Trigger } from './trigger.js?v=20250719';

export class Timer {
  constructor(periodMs = 1000) {
    this._trigger = new Trigger();
    this._period = periodMs;
    this._timerId = null;
    this._start();
  }

  _start() {
    if (this._timerId !== null) return;
    this._timerId = setInterval(() => {
      this._trigger.trigger();
    }, this._period);
  }

  wait() {
    return this._trigger.wait(); 
  }

  stop() {
    if (this._timerId !== null) {
      clearInterval(this._timerId);
      this._timerId = null;
    }
  }

  restart(periodMs = this._period) {
    this.stop();
    this._period = periodMs;
    this._start();
  }
}
