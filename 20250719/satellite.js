import * as THREE from 'three';

const earthRadiusKm = 6371;

export class Satellite {
	constructor(scene) {
		this.scene = scene;
		this.footprintCircle = null;
		this.orbitLine = null;

		// const satMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000 });
		// const satGeometry = this.createEmojiSprite('🛰️');
		this.satelliteMesh = this.createEmojiSprite('🛰️');
		this.orbitMaterial = new THREE.LineBasicMaterial({ color: 0xffaa00 });

		scene.add(this.satelliteMesh);
	}

	update(data) {
		const { lat, lon } = data.position;
		const x = lon / 180;
		const y = lat / 180;
		this.satelliteMesh.position.set(x, y, 0.02);

		if (this.footprintCircle) {
			this.scene.remove(this.footprintCircle);
		}
		this.footprintCircle = createFootprintCircle(lat, lon, data.footprint_km);
		this.scene.add(this.footprintCircle);

		if (this.orbitLine) {
			this.scene.remove(this.orbitLine);
		}
		this.orbitLine = createOrbitLineWithWraps(data.orbit, this.orbitMaterial);
		this.scene.add(this.orbitLine);
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

function mirrorLon(ssplon, rangelon) {
	const mapBreak = -180;

	let warped = false;

	// Compute diff = ssplon - rangelon wrapped to [0,360)
	let diff = ssplon - rangelon;
	while (diff < 0) diff += 360;
	while (diff >= 360) diff -= 360;

	let mlon = ssplon + Math.abs(diff);
	while (mlon > 180) mlon -= 360;
	while (mlon < -180) mlon += 360;

	if (
		(ssplon >= mapBreak && ssplon < mapBreak + 180) ||
		(ssplon < mapBreak - 180 && ssplon >= mapBreak - 360)
	) {
		if (
			(rangelon >= mapBreak && rangelon < mapBreak + 180) ||
			(rangelon < mapBreak - 180 && rangelon >= mapBreak - 360)
		) {
			// same half-map, no warp
		} else {
			warped = true;
		}
	} else {
		if (
			(mlon >= mapBreak && mlon < mapBreak + 180) ||
			(mlon < mapBreak - 180 && mlon >= mapBreak - 360)
		) {
			warped = true;
		}
	}

	return { mlon, warped };
}


/**
 * Create footprint circle points in lon/lat degrees.
 * Mirrors the points on longitude.
 * Detects if footprint crosses dateline and splits if needed.
 *
 * Returns { numParts: 1 or 2, points1: [...], points2?: [...] }
 */
function computeFootprintPoints(latDeg, lonDeg, footprintKm) {

	latDeg = normalizeLat(latDeg);
	lonDeg = normalizeLon(lonDeg);

	const ssplat = deg2rad(latDeg);
	const ssplon = deg2rad(lonDeg);
	const beta = footprintKm / earthRadiusKm;

	const leftLon = -180;

	// We generate 180 points for half the circle and mirror for the other half
	const points = new Array(360);

	let warped = false;

	for (let azi = 0; azi < 180; azi++) {
		const azimuth = deg2rad(azi);

		const rangelat = Math.asin(
			Math.sin(ssplat) * Math.cos(beta) +
			Math.cos(azimuth) * Math.sin(beta) * Math.cos(ssplat)
		);

		const num = Math.cos(beta) - Math.sin(ssplat) * Math.sin(rangelat);
		const dem = Math.cos(ssplat) * Math.cos(rangelat);

		let rangelon;
		if (azi === 0 && northPoleIsCovered(latDeg, lonDeg, footprintKm)) {
			rangelon = ssplon + Math.PI;
		} else if (Math.abs(num / dem) > 1.0) {
			rangelon = ssplon;
		} else {
			if ((180.0 - azi) >= 0) {
				rangelon = ssplon - arccos(num, dem);
			} else {
				rangelon = ssplon + arccos(num, dem);
			}
		}

		while (rangelon < -Math.PI) rangelon += 2 * Math.PI;
		while (rangelon > Math.PI) rangelon -= 2 * Math.PI;

		const rangelatDeg = rad2deg(rangelat);
		const rangelonDeg = rad2deg(rangelon);

		const { mlon, warped: pointWarped } = mirrorLon(lonDeg, rangelonDeg, -180);
		warped = warped || pointWarped;

		points[azi] = { lon: rangelonDeg, lat: rangelatDeg };
		points[359 - azi] = { lon: mlon, lat: rangelatDeg };
	}


	if (poleIsCovered(latDeg, lonDeg, footprintKm)) {
		/* pole is covered => sort points1 and add additional points */
		sort_points_lon(latDeg, lonDeg, points);
		// console.log("Pole is covered, points sorted by longitude");
		return { numParts: 1, points1: points };
	} else if (warped) {
		/* pole not covered but range circle has been warped => split points */
		const [points1, points2] = split_points(latDeg, lonDeg, points);
		return { numParts: 2, points1: points1, points2: points2 };
	}
	else {
		/* the nominal condition => points1 is adequate */
		return { numParts: 1, points1: points };
	}
}

function split_points(latDeg, lonDeg, points1) {
	/* initialize parameters */
	let n = points1.length;
	let n1 = 0;
	let n2 = 0;
	let i = 0;
	let j = 0;
	let k = 0;
	let ns = 0;
	let tps1 = [];
	let tps2 = [];

	if ((lonDeg >= 179.4) || (lonDeg <= -179.4)) {
		/* sslon = +/-180 deg.
		   - copy points with (x > satmap->x0+satmap->width/2) to tps1
		   - copy points with (x < satmap->x0+satmap->width/2) to tps2
		   - sort tps1 and tps2
		 */
		for (i = 0; i < n; i++) {
			if (points1[i].lon > 0) {
				tps1.push(points1[i]);
				n1++;
			}
			else {
				tps2.push(points1[i]);
				n2++;
			}
		}

		sort_points_lat(latDeg, lonDeg, tps1);
		sort_points_lat(latDeg, lonDeg, tps2);
	}
	else if (lonDeg < 0) {
		/* We are on the left side of the map.
		   Scan through points1 until we get to x > sspx (i=ns):

		   - copy the points forwards until x < (x0+w/2) => tps2
		   - continue to copy until the end => tps1
		   - copy the points from i=0 to i=ns => tps1.

		   Copy tps1 => points1 and tps2 => points2
		 */
		while (points1[i].lon <= 0) {
			i++;
		}
		ns = i - 1;

		while (points1[i].lon > 0) {
			tps2.push(points1[i]);
			i++;
			j++;
			n2++;
		}

		while (i < n) {
			tps1.push(points1[i]);
			i++;
			k++;
			n1++;
		}

		for (i = 0; i <= ns; i++) {
			tps1.push(points1[i]);
			k++;
			n1++;
		}
	}
	else {
		// console.log('split 3')
		/* We are on the right side of the map.
		   Scan backwards through points1 until x < sspx (i=ns):

		   - copy the points i=ns,i-- until x >= x0+w/2  => tps2
		   - copy the points until we reach i=0          => tps1
		   - copy the points from i=n to i=ns            => tps1

		 */
		i = n - 1;
		while (points1[i].lon >= 0) {
			i--;
		}
		ns = i + 1;

		while (points1[i].lon < 0) {
			tps2.push(points1[i]);
			i--;
			j++;
			n2++;
		}

		while (i >= 0) {
			tps1.push(points1[i]);
			i--;
			k++;
			n1++;
		}

		for (i = n - 1; i >= ns; i--) {
			tps1.push(points1[i]);
			k++;
			n1++;
		}
	}

	//g_print ("NS:%d  N1:%d  N2:%d\n", ns, n1, n2);

	/* free points and copy new contents */
	points1 = tps1.slice(0, n1);
	let points2 = tps2.slice(0, n2);

	/* stretch end points to map borders */
	if (points1[0].lon > 0) {
		points1[0].lon = 180;
		points1[n1 - 1].lon = 180;
		points2[0].lon = -180;
		points2[n2 - 1].lon = -180;
	}
	else {
		points2[0].lon = 180;
		points2[n2 - 1].lon = 180;
		points1[0].lon = -180;
		points1[n1 - 1].lon = -180;
	}

	return [points1, points2];
}

function sort_points_lon(latDeg, lonDeg, points) {
	points.sort((a, b) => a.lon - b.lon);

	/* move point at position 0 to position 1 */
	points[1] = { lon: -180, lat: points[0].lat };

	/* move point at position N to position N-1 */
	points[points.length - 2].lon = 180;
	points[points.length - 2].lat = points[points.length - 1].lat;

	// console.log(`sort_points_lon: latDeg=${latDeg}, lonDeg=${lonDeg}`);
	if (latDeg > 0.0) {
		/* insert (x0-1,y0) into position 0 */
		points[0].lon = -180;
		points[0].lat = 90;

		/* insert (x0+width,y0) into position N */
		points[points.length - 1].lon = 180;
		points[points.length - 1].lat = 90;
	}
	else {
		// console.log('sort_points_lon: lonDeg <= 0.0');
		/* insert (x0,y0+height) into position 0 */
		points[0].lon = -180;
		points[0].lat = -90;

		/* insert (x0+width,y0+height) into position N */
		points[points.length - 1].lon = 180;
		points[points.length - 1].lat = -90;
	}

}

function sort_points_lat(latDeg, lonDeg, points) {
	points.sort((a, b) => a.lat - b.lat);
}

function deg2rad(deg) {
	return deg * Math.PI / 180;
}

function rad2deg(rad) {
	return rad * 180 / Math.PI;
}

function normalizeLon(lon) {
	while (lon < -180) lon += 360;
	while (lon > 180) lon -= 360;
	return lon;
}

function normalizeLat(lat) {
	if (lat > 90) {
		lat = 180 - lat;
	} else if (lat < -90) {
		lat = -180 - lat;
	}
	return lat;
}

function arccos(num, dem) {
	const val = num / dem;
	return Math.acos(Math.min(1, Math.max(-1, val)));
}


// Haversine formula for distance in km between two lat/lon points
function haversineDistance(lat1, lon1, lat2, lon2) {
	const dLat = deg2rad(lat2 - lat1);
	const dLon = deg2rad(lon2 - lon1);
	const a = Math.sin(dLat / 2) ** 2 +
		Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) *
		Math.sin(dLon / 2) ** 2;
	const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
	return earthRadiusKm * c;
}

function northPoleIsCovered(latDeg, lonDeg, footprintKm) {
	const dist = haversineDistance(latDeg, lonDeg, 90, 0);
	return dist <= footprintKm;
}

function southPoleIsCovered(latDeg, lonDeg, footprintKm) {
	const dist = haversineDistance(latDeg, lonDeg, -90, 0);
	return dist <= footprintKm;
}

function poleIsCovered(latDeg, lonDeg, footprintKm) {
	return northPoleIsCovered(latDeg, lonDeg, footprintKm) || southPoleIsCovered(latDeg, lonDeg, footprintKm);
}

function createFootprintCircle(latDeg, lonDeg, footprintKm) {
	const footprintData = computeFootprintPoints(latDeg, lonDeg, footprintKm);
	const group = new THREE.Group();

	const material = new THREE.MeshBasicMaterial({
		color: 0xffffff,
		opacity: 0.3,
		transparent: true,
		side: THREE.DoubleSide,
		depthTest: false,
	});

	function createMeshFromPoints(points) {
		if (points.length === 0) return null;

		const shape = new THREE.Shape();

		points = points.map(p => ({
			lon: p.lon / 180,
			lat: p.lat / 180
		}));
		shape.moveTo(points[0].lon, points[0].lat);

		for (let i = 1; i < points.length; i++) {
			shape.lineTo(points[i].lon, points[i].lat);
		}
		const geometry = new THREE.ShapeGeometry(shape);
		const mesh = new THREE.Mesh(geometry, material);
		return mesh;
	}

	const mesh1 = createMeshFromPoints(footprintData.points1);
	if (mesh1) group.add(mesh1);

	if (footprintData.numParts === 2 && footprintData.points2) {
		const mesh2 = createMeshFromPoints(footprintData.points2);
		if (mesh2) group.add(mesh2);
	}

	return group;
}


function createOrbitLineWithWraps(flatCoords, orbitMaterial) {
	const group = new THREE.Group();
	let segmentPoints = [];
	let lastLon = null;

	for (let i = 0; i < flatCoords.length; i += 2) {
		const lat = flatCoords[i];
		const lon = flatCoords[i + 1];

		const x = lon / 180;
		const y = lat / 180;

		if (lastLon !== null && Math.abs(lon - lastLon) > 180) {
			// Longitude wrap-around detected, break segment
			if (segmentPoints.length > 1) {
				const geometry = new THREE.BufferGeometry().setFromPoints(segmentPoints);
				const line = new THREE.Line(geometry, orbitMaterial);
				group.add(line);
			}
			segmentPoints = [];
		}

		segmentPoints.push(new THREE.Vector3(x, y, 0.01));
		lastLon = lon;
	}

	if (segmentPoints.length >= 2) {
		const geometry = new THREE.BufferGeometry().setFromPoints(segmentPoints);
		const line = new THREE.Line(geometry, orbitMaterial);
		group.add(line);
	}

	return group;
}