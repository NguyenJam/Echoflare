import * as THREE from 'three';

export class RenderLoop {

	constructor(scene, container) {
		this.scene = scene;

		this.canvas = document.createElement('canvas');
		container.appendChild(this.canvas);

		this.canvas.style.width = '100%';
		this.canvas.style.aspectRatio = '2 / 1';
		this.canvas.style.maxHeight = '100%';
		this.canvas.style.maxWidth = '100%';
		this.canvas.style.height = 'auto';
		this.canvas.style.display = 'block';
	}

	async run(ctx) {
		const renderer = new THREE.WebGLRenderer({ canvas: this.canvas });

		const camera = new THREE.OrthographicCamera(-1, 1, 0.5, -0.5, 0.1, 10);
		camera.position.z = 2;

		return new Promise(resolve => {
			const tick = () => {
				if (ctx.cancelled()) {
					resolve();
					return;
				}

				const width = this.canvas.clientWidth;
				const height = this.canvas.clientHeight;

				if (this.canvas.width !== width || this.canvas.height !== height) {
					renderer.setSize(width, height, false);
					camera.left = -1;
					camera.right = 1;
					camera.top = 0.5;
					camera.bottom = -0.5;
					camera.updateProjectionMatrix();
				}
				renderer.render(this.scene, camera);

				requestAnimationFrame(() => tick());
			}
			tick();
		});
	}
}
