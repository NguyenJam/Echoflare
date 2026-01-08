import * as THREE from 'three';

export class GroundStation {
	constructor(scene, emoji = '📡') {
		this.scene = scene;
		this.emoji = emoji;
		this.baseStationSprite = this.createEmojiSprite(emoji);
		scene.add(this.baseStationSprite);

	}

	update(data) {
		if (data.ground_station) {
			const { lat, lon } = data.ground_station;
			const x = lon / 180;
			const y = lat / 180;
			this.baseStationSprite.position.set(x, y, 0.02);
		}
	}

	createEmojiSprite(emoji) {
		const canvas = document.createElement('canvas');
		const size = 64; // Size of the canvas
		canvas.width = canvas.height = size;

		const ctx = canvas.getContext('2d');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.font = `${size * 0.8}px sans-serif`;
		ctx.fillText(emoji, size / 2, size / 2);

		const texture = new THREE.CanvasTexture(canvas);
		texture.minFilter = THREE.NearestFilter;
		texture.magFilter = THREE.NearestFilter;
		texture.generateMipmaps = false;
		const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
		const sprite = new THREE.Sprite(material);

		sprite.scale.set(0.05, 0.05, 1); 

		return sprite;
	}


}