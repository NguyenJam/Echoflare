import * as THREE from 'three';

export class Map {
    constructor(scene, map="map.jpg") {

        const textureLoader = new THREE.TextureLoader();
        textureLoader.load(map, (texture) => {
            const geometry = new THREE.PlaneGeometry(2, 1);
            const material = new THREE.MeshBasicMaterial({ map: texture });
            const plane = new THREE.Mesh(geometry, material);
            scene.add(plane);
            scene.add(createGridLines());
        });
    }
}

function createTextSprite(message, x, y) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    const fontSize = 48;
    canvas.width = 256;
    canvas.height = 128;
    context.font = `${fontSize}px sans-serif`;
    context.fillStyle = '#888888';
    context.textAlign = 'right';
    context.textBaseline = 'middle';
    context.fillText(message, canvas.width - 10, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(0.15, 0.075, 1);
    sprite.position.set(x, y, 0.01);

    return sprite;
}

function createGridLines() {
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x888888 });
    const gridGroup = new THREE.Group();
    // Horizontal lines (latitude)
    for (let lat = -67.5; lat <= 67.5; lat += 22.5) {
        const y = lat / 180;
        const geometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(-1, y, 0.02),
            new THREE.Vector3(1, y, 0.02)
        ]);
        gridGroup.add(new THREE.Line(geometry, lineMaterial));
        gridGroup.add(createTextSprite(`${lat}°`, -0.99, y + 0.025));
    }

    // Vertical lines (longitude)
    for (let lon = -150; lon <= 150; lon += 30) {
        const x = lon / 180;
        const geometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(x, -0.5, 0.02),
            new THREE.Vector3(x, 0.5, 0.02)
        ]);
        gridGroup.add(new THREE.Line(geometry, lineMaterial));
        gridGroup.add(createTextSprite(`${lon}°`, x - 0.08, -0.48));
    }
    return gridGroup
}