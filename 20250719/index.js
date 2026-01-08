import * as THREE from 'three';
import { Satellite } from './satellite.js?v=20250719';
import { Radio } from './radio.js?v=20250719';
import { Map } from './map.js?v=20250719';
import { Ctx } from './ctx.js?v=20250719';
import { SatelliteTracker } from './satellite-tracker.js?v=20250719';
import { RenderLoop } from './render-loop.js?v=20250719';
import { RadioControl } from './radio-control.js?v=20250719';
import { SatelliteInfoPanel } from './satellite-info-panel.js?v=20250719';
import { GroundStation } from './ground-station.js?v=20250719';
import { SatelliteSelector } from './satellite-selector.js?v=20250719';
import { BriefingManager } from './briefing-control.js?v=20250719';

function main(options = {}) {
	const ctx = new Ctx();

	const controls = createControls(options.container);
	const viewer = createViewer(options.container);
	
	const scene = new THREE.Scene();

	const satelliteTracker = new SatelliteTracker("/satellite");
	const satelliteCtl = new Satellite(scene);
	const groundStation = new GroundStation(scene);
	const map = new Map(scene, "map.jpg", );
	const renderLoop = new RenderLoop(scene, viewer);

	satelliteTracker.onData((data) => {
		satelliteCtl.update(data);
		infoPanel.update(data);
		groundStation.update(data);
		radioCtl.setFrequency(data.downlink_mhz + data.doppler_hz / 1000000);
	});



	const radio = new Radio("/radio");
	const radioCtl = new RadioControl(controls);
	radioCtl.onPowerChange = async (power) => {
		if (power) {
			radio.powerOn();
		} else {
			radio.powerOff();
		}
	};

    radio.onStatusChange = (status) => {
        radioCtl.setStatus(status);
    }
	
	radioCtl.onTransmit = async (file) => {
		await radio.transmit(file);
	};

	const satelliteSelector = new SatelliteSelector(controls, "/satellite");
	satelliteSelector.onSatelliteSelected = (satelliteId) => {
		satelliteTracker.setSatellite(satelliteId);
		radio.setSatellite(satelliteId);
	};

    const briefing = new BriefingManager(controls);

	const infoPanel = new SatelliteInfoPanel(viewer, "/satellite");


	return Promise.all([
		satelliteTracker.run(ctx),
		renderLoop.run(ctx),
	]);
}


function createTitle(container) {
	const title = document.createElement('span');
	title.textContent = 'GroundTrack';
	container.appendChild(title);
	return title;
}

function createControls(container) {
	const controls = document.createElement('div');
	controls.style.padding = '0.5rem';
	controls.style.background = '#222';
	controls.style.color = '#fff';
	controls.style.display = 'flex';
	controls.style.alignItems = 'center';
	controls.style.justifyContent = 'space-between';
	container.appendChild(controls);
	return controls;
}


function createViewer(container) {
	const viewer = document.createElement('div');
	viewer.style.flex = '1';
	viewer.style.display = 'flex';
	viewer.style.justifyContent = 'center';
	viewer.style.alignItems = 'center';
	viewer.style.background = 'black';
	container.appendChild(viewer);
	return viewer
}

export default main;