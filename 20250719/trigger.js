export class Trigger {
  #promise = null;
  #resolve = null;
  #signaled = false;

  wait() {
    if (this.#signaled) {
      this.#signaled = false;
      return Promise.resolve();
    }

    if (!this.#promise) {
      this.#promise = new Promise((resolve) => {
        this.#resolve = () => {
          this.#promise = null;
          this.#resolve = null;
          resolve();
        };
      });
    }

    return this.#promise;
  }

  trigger() {
    if (this.#resolve) {
      this.#resolve(); // will clear promise/resolve inside
    } else {
      this.#signaled = true;
    }
  }
}
