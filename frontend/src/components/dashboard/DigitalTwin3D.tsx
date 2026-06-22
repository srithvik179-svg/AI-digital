'use client';

/**
 * Phase 48 — 3D Digital Twin Visualization
 *
 * A fully interactive Three.js laptop model that renders live telemetry:
 *
 *  🌡  TEMPERATURE ZONES
 *     Six heat zones (CPU die, GPU, battery, SSD, RAM, exhaust vent) shift
 *     from cool blue → amber → red as temperature climbs. Each zone is a
 *     dedicated MeshStandardMaterial with emissive intensity driven by temp.
 *
 *  ⚡  BATTERY STATUS
 *     A translucent battery body on the underside fills with glowing green /
 *     amber / red light proportional to charge level. Low battery triggers
 *     a slow crimson pulse.
 *
 *  🖥  CPU STATE
 *     The CPU die zone pulses with a radial glow driven by cpu_usage.
 *     Heavy load → rapid deep-red throb. Idle → slow cool-blue breath.
 *
 *  🎮  INTERACTION
 *     OrbitControls: drag to rotate, scroll to zoom, right-drag to pan.
 *     Click any heat zone to get a pop-up tooltip with the exact reading.
 *     Toggle bottom/top view buttons for quick preset camera angles.
 *
 *  📡  LIVE DATA
 *     Subscribes to GET /api/v1/live-stream/sse (EventSource).
 *     Falls back to polling GET /api/v1/telemetry/?limit=1 every 3 s
 *     when SSE is unavailable.
 *
 * Dependencies: three, @types/three (already installed).
 * No external 3D model files — geometry is constructed procedurally.
 */

import React, {
  useEffect, useRef, useState, useCallback,
} from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface TelemetryState {
  cpu_usage:           number;   // 0-100
  cpu_temperature:     number;   // °C
  gpu_usage:           number;   // 0-100
  gpu_temperature:     number;   // °C
  memory_usage:        number;   // 0-100
  battery_level:       number;   // 0-100
  battery_health:      number;   // 0-100
  battery_temperature: number;   // °C
  disk_usage:          number;   // 0-100
  fan_speed:           number;   // RPM
  signal_strength_dbm: number;   // negative dBm
  power_source:        string;   // 'ac' | 'battery'
  thermal_state:       string;   // 'nominal' | 'moderate' | 'serious' | 'critical'
  device_id:           string;
  source:              string;
  timestamp:           string;
}

interface ZoneInfo {
  name:    string;
  metric:  string;
  value:   number;
  unit:    string;
  x:       number;   // screen px
  y:       number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const API = 'http://localhost:8000/api/v1';

const DEFAULT_TELEMETRY: TelemetryState = {
  cpu_usage:           35,
  cpu_temperature:     52,
  gpu_usage:           18,
  gpu_temperature:     48,
  memory_usage:        52,
  battery_level:       78,
  battery_health:      92,
  battery_temperature: 30,
  disk_usage:          42,
  fan_speed:           1800,
  signal_strength_dbm: -62,
  power_source:        'ac',
  thermal_state:       'nominal',
  device_id:           'demo',
  source:              'mac',
  timestamp:           new Date().toISOString(),
};

// Temperature → color (cool blue → green → amber → red → white-hot)
function tempToColor(temp: number, minT = 30, maxT = 100): THREE.Color {
  const t = Math.max(0, Math.min(1, (temp - minT) / (maxT - minT)));
  if (t < 0.33)  return new THREE.Color().lerpColors(new THREE.Color(0x1d4ed8), new THREE.Color(0x10b981), t / 0.33);
  if (t < 0.66)  return new THREE.Color().lerpColors(new THREE.Color(0x10b981), new THREE.Color(0xf59e0b), (t - 0.33) / 0.33);
  return new THREE.Color().lerpColors(new THREE.Color(0xf59e0b), new THREE.Color(0xff2200), (t - 0.66) / 0.34);
}

// Usage (0-100) → emissive intensity
function usageToEmissive(usage: number): number {
  return 0.05 + (usage / 100) * 0.8;
}

// Battery level → color
function batteryColor(level: number): THREE.Color {
  if (level > 50) return new THREE.Color(0x10b981);
  if (level > 20) return new THREE.Color(0xf59e0b);
  return new THREE.Color(0xef4444);
}

// ─────────────────────────────────────────────────────────────────────────────
// Three.js scene builder (all geometry is procedural)
// ─────────────────────────────────────────────────────────────────────────────

function buildScene(canvas: HTMLCanvasElement) {

  /* ── Renderer ── */
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
  renderer.toneMapping       = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;

  /* ── Scene ── */
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0f1a);
  scene.fog        = new THREE.Fog(0x0a0f1a, 12, 25);

  /* ── Camera ── */
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(0, 5.5, 8.5);
  camera.lookAt(0, 0.5, 0);

  /* ── Orbit controls ── */
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping    = true;
  controls.dampingFactor    = 0.08;
  controls.minDistance      = 4;
  controls.maxDistance      = 18;
  controls.maxPolarAngle    = Math.PI * 0.85;
  controls.target.set(0, 0.5, 0);

  /* ── Lighting ── */
  const ambient = new THREE.AmbientLight(0x1a2744, 0.8);
  scene.add(ambient);

  const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
  keyLight.position.set(4, 8, 6);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  keyLight.shadow.camera.near = 0.5;
  keyLight.shadow.camera.far  = 50;
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0x4080ff, 0.4);
  fillLight.position.set(-5, 3, -4);
  scene.add(fillLight);

  const rimLight = new THREE.SpotLight(0x6366f1, 1.2, 20, Math.PI / 6);
  rimLight.position.set(-3, 6, -5);
  scene.add(rimLight);

  /* ── Materials ── */
  const chassisMat = new THREE.MeshStandardMaterial({
    color: 0x1a1a2e, metalness: 0.85, roughness: 0.25,
    envMapIntensity: 0.6,
  });
  const screenBezzelMat = new THREE.MeshStandardMaterial({
    color: 0x0d0d14, metalness: 0.9, roughness: 0.2,
  });
  const screenMat = new THREE.MeshStandardMaterial({
    color:    0x050d1a,
    emissive: new THREE.Color(0x1a3a6b),
    emissiveIntensity: 0.5,
    roughness: 0.05, metalness: 0.0,
  });
  const keyboardMat = new THREE.MeshStandardMaterial({
    color: 0x0a0a14, metalness: 0.5, roughness: 0.7,
  });
  const glassBottomMat = new THREE.MeshStandardMaterial({
    color: 0x111827, metalness: 0.3, roughness: 0.6,
  });

  /* ══════════════════════════════════════════════════════════════════════════
     LAPTOP BASE (bottom chassis)
     14" form factor: 31 cm × 1.4 cm × 20 cm  →  scaled in Three.js units
     ══════════════════════════════════════════════════════════════════════════ */
  const BASE_W = 3.2, BASE_H = 0.14, BASE_D = 2.2;

  const baseGeo  = new THREE.BoxGeometry(BASE_W, BASE_H, BASE_D, 4, 1, 3);
  const baseMesh = new THREE.Mesh(baseGeo, chassisMat);
  baseMesh.position.y = BASE_H / 2;
  baseMesh.castShadow    = true;
  baseMesh.receiveShadow = true;
  baseMesh.name = 'base';
  scene.add(baseMesh);

  /* Rubber feet */
  const footGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.015, 12);
  const footMat = new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.9 });
  [[-1.4, -0.9], [-1.4, 0.9], [1.4, -0.9], [1.4, 0.9]].forEach(([x, z]) => {
    const foot = new THREE.Mesh(footGeo, footMat);
    foot.position.set(x, 0, z);
    scene.add(foot);
  });

  /* ══════════════════════════════════════════════════════════════════════════
     LID (screen unit) — hinged at the back edge
     ══════════════════════════════════════════════════════════════════════════ */
  const LID_W = 3.18, LID_H = 2.05, LID_D = 0.09;
  const LID_OPEN_ANGLE = -Math.PI * 0.52;   // ~110° open

  const lidGroup = new THREE.Group();
  lidGroup.position.set(0, BASE_H, -BASE_D / 2);  // hinge at back of base
  scene.add(lidGroup);

  const lidGeo  = new THREE.BoxGeometry(LID_W, LID_H, LID_D);
  const lidMesh = new THREE.Mesh(lidGeo, chassisMat);
  lidMesh.position.set(0, LID_H / 2, -LID_D / 2);
  lidMesh.castShadow = true;
  lidMesh.name = 'lid';
  lidGroup.add(lidMesh);

  // Screen bezel (front face of lid)
  const bezelGeo  = new THREE.BoxGeometry(LID_W - 0.04, LID_H - 0.04, 0.012);
  const bezelMesh = new THREE.Mesh(bezelGeo, screenBezzelMat);
  bezelMesh.position.set(0, LID_H / 2, -(LID_D - 0.004));
  bezelMesh.name = 'bezel';
  lidGroup.add(bezelMesh);

  // Actual screen panel
  const screenGeo  = new THREE.PlaneGeometry(LID_W - 0.28, LID_H - 0.28);
  const screenMesh = new THREE.Mesh(screenGeo, screenMat);
  screenMesh.position.set(0, LID_H / 2, -(LID_D - 0.016));
  screenMesh.name = 'screen';
  lidGroup.add(screenMesh);

  // Screen glow overlay (emissive)
  const glowGeo = new THREE.PlaneGeometry(LID_W - 0.28, LID_H - 0.28);
  const glowMat = new THREE.MeshBasicMaterial({
    color: 0x1a4a9b, transparent: true, opacity: 0.15, depthWrite: false,
  });
  const glowMesh = new THREE.Mesh(glowGeo, glowMat);
  glowMesh.position.set(0, LID_H / 2, -(LID_D - 0.018));
  glowMesh.name = 'screenGlow';
  lidGroup.add(glowMesh);

  // Apple-style logo indent
  const logoDisk = new THREE.CylinderGeometry(0.22, 0.22, 0.005, 32);
  const logoMat  = new THREE.MeshStandardMaterial({
    color: 0xdddddd, metalness: 1.0, roughness: 0.1,
    emissive: new THREE.Color(0xffffff), emissiveIntensity: 0.0,
  });
  const logoMesh = new THREE.Mesh(logoDisk, logoMat);
  logoMesh.rotation.x = Math.PI / 2;
  logoMesh.position.set(0, LID_H / 2, 0.048);
  logoMesh.name = 'logo';
  lidGroup.add(logoMesh);

  // Apply lid open angle
  lidGroup.rotation.x = LID_OPEN_ANGLE;

  /* ══════════════════════════════════════════════════════════════════════════
     KEYBOARD DECK (top of base)
     ══════════════════════════════════════════════════════════════════════════ */
  const deckGeo  = new THREE.PlaneGeometry(BASE_W - 0.08, BASE_D - 0.1);
  const deckMesh = new THREE.Mesh(deckGeo, keyboardMat);
  deckMesh.rotation.x = -Math.PI / 2;
  deckMesh.position.set(0, BASE_H + 0.001, 0.04);
  deckMesh.receiveShadow = true;
  deckMesh.name = 'deck';
  scene.add(deckMesh);

  // Trackpad
  const trackpadGeo = new THREE.BoxGeometry(0.85, 0.004, 0.58);
  const trackpadMat = new THREE.MeshStandardMaterial({
    color: 0x18182a, metalness: 0.6, roughness: 0.3,
  });
  const trackpadMesh = new THREE.Mesh(trackpadGeo, trackpadMat);
  trackpadMesh.position.set(0, BASE_H + 0.003, 0.7);
  scene.add(trackpadMesh);

  // Speaker grilles (left + right)
  for (let side = -1; side <= 1; side += 2) {
    const speakerGeo = new THREE.BoxGeometry(0.06, 0.004, 0.55);
    const speakerMat = new THREE.MeshStandardMaterial({ color: 0x0a0a14, roughness: 1.0 });
    const speakerMesh = new THREE.Mesh(speakerGeo, speakerMat);
    speakerMesh.position.set(side * 1.52, BASE_H + 0.003, 0.0);
    scene.add(speakerMesh);
  }

  /* ══════════════════════════════════════════════════════════════════════════
     HEAT ZONES — 6 painted zones on the underside of the base
     Each zone = a flat plane slightly below the base, with emissive material
     ══════════════════════════════════════════════════════════════════════════ */

  interface HeatZone {
    name:     string;
    position: [number, number, number];
    size:     [number, number];
    mat:      THREE.MeshStandardMaterial;
    mesh:     THREE.Mesh;
    label:    string;
    getTemp:  (t: TelemetryState) => number;
    minT:     number;
    maxT:     number;
  }

  const zoneDefs = [
    {
      name: 'cpu',     label: 'CPU Die',      x: -0.6,  z: -0.3, w: 0.7,  d: 0.6,
      getTemp: (t: TelemetryState) => t.cpu_temperature, minT: 30, maxT: 100,
    },
    {
      name: 'gpu',     label: 'GPU',          x:  0.5,  z: -0.3, w: 0.55, d: 0.5,
      getTemp: (t: TelemetryState) => t.gpu_temperature, minT: 30, maxT: 95,
    },
    {
      name: 'battery', label: 'Battery',      x:  0.2,  z:  0.65, w: 1.9,  d: 0.7,
      getTemp: (t: TelemetryState) => t.battery_temperature, minT: 20, maxT: 55,
    },
    {
      name: 'ram',     label: 'RAM',          x: -1.0,  z: -0.3, w: 0.36, d: 0.5,
      getTemp: (t: TelemetryState) => t.cpu_temperature * 0.75, minT: 25, maxT: 80,
    },
    {
      name: 'ssd',     label: 'SSD',          x:  1.1,  z: -0.3, w: 0.36, d: 0.5,
      getTemp: (t: TelemetryState) => t.cpu_temperature * 0.7,  minT: 25, maxT: 80,
    },
    {
      name: 'exhaust', label: 'Exhaust',      x: -0.6,  z: -0.95, w: 1.5,  d: 0.28,
      getTemp: (t: TelemetryState) => t.cpu_temperature * 1.08, minT: 30, maxT: 110,
    },
  ];

  const heatZones: HeatZone[] = zoneDefs.map(def => {
    const mat = new THREE.MeshStandardMaterial({
      color:             new THREE.Color(0x1d4ed8),
      emissive:          new THREE.Color(0x1d4ed8),
      emissiveIntensity: 0.1,
      transparent:       true,
      opacity:           0.78,
      roughness:         0.6,
      metalness:         0.1,
      depthWrite:        false,
    });
    const geo  = new THREE.PlaneGeometry(def.w, def.d);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(def.x, BASE_H + 0.002, def.z);
    mesh.name = `zone_${def.name}`;
    mesh.userData = { zoneName: def.name, label: def.label };
    scene.add(mesh);
    return { ...def, mat, mesh, position: [def.x, BASE_H + 0.002, def.z] as [number, number, number], size: [def.w, def.d] as [number, number] };
  });

  /* ══════════════════════════════════════════════════════════════════════════
     BATTERY BODY — glowing fill tube inside the base (visible from side)
     ══════════════════════════════════════════════════════════════════════════ */
  const batBodyGeo = new THREE.BoxGeometry(1.85, 0.06, 0.68);
  const batBodyMat = new THREE.MeshStandardMaterial({
    color: 0x0a0a1e, metalness: 0.1, roughness: 0.8,
    transparent: true, opacity: 0.5,
  });
  const batBody = new THREE.Mesh(batBodyGeo, batBodyMat);
  batBody.position.set(0.2, BASE_H - 0.01, 0.66);
  scene.add(batBody);

  // Battery fill bar (scales on X axis with level)
  const batFillGeo = new THREE.BoxGeometry(1.75, 0.045, 0.58);
  const batFillMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(0x10b981),
    emissive: new THREE.Color(0x10b981),
    emissiveIntensity: 0.6,
    transparent: true, opacity: 0.85,
  });
  const batFillMesh = new THREE.Mesh(batFillGeo, batFillMat);
  batFillMesh.position.set(0.2, BASE_H - 0.01, 0.66);
  batFillMesh.name = 'batteryFill';
  scene.add(batFillMesh);

  // Battery outline (border)
  const batEdges = new THREE.EdgesGeometry(batBodyGeo);
  const batLineMat = new THREE.LineBasicMaterial({ color: 0x334155 });
  const batLines  = new THREE.LineSegments(batEdges, batLineMat);
  batLines.position.copy(batBody.position);
  scene.add(batLines);

  /* ══════════════════════════════════════════════════════════════════════════
     CPU PULSE LIGHT — a PointLight directly above the CPU zone
     ══════════════════════════════════════════════════════════════════════════ */
  const cpuLight = new THREE.PointLight(0x6366f1, 0.8, 1.5);
  cpuLight.position.set(-0.6, BASE_H + 0.3, -0.3);
  cpuLight.name = 'cpuLight';
  scene.add(cpuLight);

  /* ══════════════════════════════════════════════════════════════════════════
     FAN RING — animated ring glyph above fan zone (RPM indicator)
     ══════════════════════════════════════════════════════════════════════════ */
  const fanRingGeo = new THREE.TorusGeometry(0.12, 0.015, 8, 32);
  const fanRingMat = new THREE.MeshStandardMaterial({
    color: 0x6366f1, emissive: new THREE.Color(0x6366f1), emissiveIntensity: 0.4,
    transparent: true, opacity: 0.7,
  });
  const fanRing = new THREE.Mesh(fanRingGeo, fanRingMat);
  fanRing.position.set(-0.6, BASE_H + 0.05, -0.95);
  fanRing.rotation.x = -Math.PI / 2;
  fanRing.name = 'fanRing';
  scene.add(fanRing);

  // 3 fan blades
  const bladeGeo = new THREE.BoxGeometry(0.02, 0.001, 0.09);
  const bladeMat = new THREE.MeshStandardMaterial({ color: 0xa5b4fc, roughness: 0.5 });
  const fanGroup = new THREE.Group();
  fanGroup.position.copy(fanRing.position);
  for (let i = 0; i < 3; i++) {
    const blade = new THREE.Mesh(bladeGeo, bladeMat);
    blade.rotation.z = (i / 3) * Math.PI * 2;
    blade.position.set(
      Math.cos((i / 3) * Math.PI * 2) * 0.06,
      0,
      Math.sin((i / 3) * Math.PI * 2) * 0.06,
    );
    fanGroup.add(blade);
  }
  scene.add(fanGroup);

  /* ══════════════════════════════════════════════════════════════════════════
     WIFI SIGNAL ARCS — 3 concentric arcs above the right-front corner
     ══════════════════════════════════════════════════════════════════════════ */
  const wifiGroup = new THREE.Group();
  wifiGroup.position.set(1.3, BASE_H + 0.05, 0.85);
  for (let i = 0; i < 3; i++) {
    const r   = 0.08 + i * 0.08;
    const arc = new THREE.TorusGeometry(r, 0.008, 6, 20, Math.PI * 0.6);
    const mat = new THREE.MeshStandardMaterial({
      color: 0x06b6d4,
      emissive: new THREE.Color(0x06b6d4),
      emissiveIntensity: 0.4 - i * 0.1,
      transparent: true, opacity: 0.6,
    });
    const arcMesh = new THREE.Mesh(arc, mat);
    arcMesh.rotation.x = -Math.PI / 2;
    arcMesh.rotation.z =  Math.PI * 0.7;
    arcMesh.userData.wifiIndex = i;
    wifiGroup.add(arcMesh);
  }
  scene.add(wifiGroup);

  /* ══════════════════════════════════════════════════════════════════════════
     GROUND REFLECTION
     ══════════════════════════════════════════════════════════════════════════ */
  const groundGeo = new THREE.PlaneGeometry(20, 20);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x060b14, metalness: 0.0, roughness: 1.0,
  });
  const ground = new THREE.Mesh(groundGeo, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.01;
  ground.receiveShadow = true;
  scene.add(ground);

  /* ══════════════════════════════════════════════════════════════════════════
     GRID HELPER (subtle)
     ══════════════════════════════════════════════════════════════════════════ */
  const grid = new THREE.GridHelper(12, 24, 0x1e3a5f, 0x0d1f33);
  grid.position.y = 0;
  scene.add(grid);

  /* ══════════════════════════════════════════════════════════════════════════
     RAYCASTER (for zone click detection)
     ══════════════════════════════════════════════════════════════════════════ */
  const raycaster = new THREE.Raycaster();
  const mouse     = new THREE.Vector2();

  const zoneMeshes = heatZones.map(z => z.mesh);

  return {
    renderer, scene, camera, controls,
    heatZones, batFillMesh, batFillMat, batBodyMat,
    cpuLight, fanGroup, wifiGroup, screenMat, glowMat: glowMesh.material as THREE.MeshBasicMaterial,
    logoMat,
    raycaster, mouse, zoneMeshes,
    dispose: () => {
      controls.dispose();
      renderer.dispose();
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Main React Component
// ─────────────────────────────────────────────────────────────────────────────

const DigitalTwin3D: React.FC = () => {
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const sceneRef    = useRef<ReturnType<typeof buildScene> | null>(null);
  const animFrameRef= useRef<number>(0);
  const startTimeRef = useRef(performance.now());

  const [telemetry, setTelemetry] = useState<TelemetryState>(DEFAULT_TELEMETRY);
  const [hoveredZone, setHoveredZone] = useState<ZoneInfo | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const [viewMode, setViewMode] = useState<'top' | 'side' | 'free'>('free');
  const [lastUpdate, setLastUpdate] = useState<string>('—');
  // mounted flag: prevents toLocaleTimeString() SSR/client timezone mismatch
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  /* ── Resize handler ──────────────────────────────────────────────────────── */
  const handleResize = useCallback(() => {
    const sc = sceneRef.current;
    if (!sc || !canvasRef.current) return;
    const w = canvasRef.current.clientWidth;
    const h = canvasRef.current.clientHeight;
    sc.renderer.setSize(w, h, false);
    sc.camera.aspect = w / h;
    sc.camera.updateProjectionMatrix();
  }, []);

  /* ── Camera preset buttons ───────────────────────────────────────────────── */
  const setView = useCallback((mode: 'top' | 'side' | 'free') => {
    const sc = sceneRef.current;
    if (!sc) return;
    setViewMode(mode);
    const { camera, controls } = sc;
    if (mode === 'top') {
      camera.position.set(0, 11, 0.01);
      camera.lookAt(0, 0, 0);
      controls.target.set(0, 0, 0);
    } else if (mode === 'side') {
      camera.position.set(7, 2, 0);
      camera.lookAt(0, 0.5, 0);
      controls.target.set(0, 0.5, 0);
    } else {
      camera.position.set(0, 5.5, 8.5);
      camera.lookAt(0, 0.5, 0);
      controls.target.set(0, 0.5, 0);
    }
    controls.update();
  }, []);

  /* ── Click → zone tooltip ────────────────────────────────────────────────── */
  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const sc = sceneRef.current;
    if (!sc || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    sc.mouse.x = ((e.clientX - rect.left) / rect.width)  * 2 - 1;
    sc.mouse.y = -((e.clientY - rect.top)  / rect.height) * 2 + 1;
    sc.raycaster.setFromCamera(sc.mouse, sc.camera);
    const hits = sc.raycaster.intersectObjects(sc.zoneMeshes);
    if (hits.length > 0) {
      const mesh = hits[0].object as THREE.Mesh;
      const def = sc.heatZones.find(z => z.mesh === mesh);
      if (def) {
        const temp = def.getTemp(telemetry);
        setHoveredZone({
          name:  def.label,
          metric:'Temperature',
          value:  Math.round(temp),
          unit:  '°C',
          x:      e.clientX - rect.left,
          y:      e.clientY - rect.top,
        });
        setTimeout(() => setHoveredZone(null), 3000);
      }
    } else {
      setHoveredZone(null);
    }
  }, [telemetry]);

  /* ── Update Three.js materials from live telemetry ───────────────────────── */
  const applyTelemetry = useCallback((t: TelemetryState) => {
    const sc = sceneRef.current;
    if (!sc) return;

    const elapsed = (performance.now() - startTimeRef.current) / 1000;

    // Heat zones
    sc.heatZones.forEach(zone => {
      const temp = zone.getTemp(t);
      const col  = tempToColor(temp, zone.minT, zone.maxT);
      zone.mat.color.copy(col);
      zone.mat.emissive.copy(col);
      zone.mat.emissiveIntensity = usageToEmissive(
        zone.name === 'cpu'     ? t.cpu_usage :
        zone.name === 'gpu'     ? t.gpu_usage :
        zone.name === 'battery' ? (100 - t.battery_level) :
        zone.name === 'exhaust' ? Math.max(t.cpu_usage, t.gpu_usage) : 30
      );
    });

    // Battery fill
    const batW = 1.75 * (t.battery_level / 100);
    sc.batFillMesh.scale.x = t.battery_level / 100;
    sc.batFillMesh.position.x = 0.2 - (1.75 - batW) / 2;
    const batCol = batteryColor(t.battery_level);
    sc.batFillMat.color.copy(batCol);
    sc.batFillMat.emissive.copy(batCol);

    // Low battery pulse
    if (t.battery_level < 20) {
      sc.batFillMat.emissiveIntensity = 0.4 + Math.sin(elapsed * 3) * 0.4;
    } else {
      sc.batFillMat.emissiveIntensity = 0.4 + (t.battery_level / 100) * 0.4;
    }

    // CPU light — color + intensity driven by load
    const cpuHeat   = t.cpu_usage / 100;
    const cpuPulseHz= 0.5 + cpuHeat * 3.0;
    const cpuCol    = tempToColor(t.cpu_temperature);
    sc.cpuLight.color.copy(cpuCol);
    sc.cpuLight.intensity = 0.4 + cpuHeat * 1.6 + Math.sin(elapsed * cpuPulseHz * Math.PI * 2) * 0.3 * cpuHeat;

    // Fan rotation speed driven by RPM
    const fanHz = (t.fan_speed / 6000) * 15;
    sc.fanGroup.rotation.y = elapsed * fanHz * Math.PI * 2;

    // WiFi arc opacity driven by signal strength
    const sigNorm = Math.max(0, Math.min(1, (t.signal_strength_dbm + 90) / 50));  // -90..-40 dBm → 0..1
    sc.wifiGroup.children.forEach((arc, i) => {
      const mat = (arc as THREE.Mesh).material as THREE.MeshStandardMaterial;
      const needed = (i + 1) / 3;     // arc 0 needs sigNorm>0.33, arc 2 needs sigNorm>1.0
      const active = sigNorm >= needed;
      mat.opacity           = active ? 0.85 : 0.12;
      mat.emissiveIntensity = active ? 0.6 + Math.sin(elapsed * 1.5 + i) * 0.2 : 0.05;
    });

    // Screen glow shifts with thermal state
    const screenGlowCol =
      t.thermal_state === 'critical' ? new THREE.Color(0x5a0000) :
      t.thermal_state === 'serious'  ? new THREE.Color(0x5a2000) :
      t.thermal_state === 'moderate' ? new THREE.Color(0x1a3060) :
                                       new THREE.Color(0x1a3a6b);
    sc.glowMat.color.copy(screenGlowCol);
    sc.glowMat.opacity = 0.12 + Math.sin(elapsed * 0.4) * 0.04;

    // Logo glow on AC
    sc.logoMat.emissiveIntensity = t.power_source === 'ac'
      ? 0.12 + Math.sin(elapsed * 0.6) * 0.06
      : 0.0;
  }, []);

  /* ── Init Three.js scene ─────────────────────────────────────────────────── */
  useEffect(() => {
    if (!canvasRef.current) return;
    const sc = buildScene(canvasRef.current);
    sceneRef.current = sc;
    handleResize();
    window.addEventListener('resize', handleResize);

    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate);
      sc.controls.update();
      sc.renderer.render(sc.scene, sc.camera);
    };
    animate();

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animFrameRef.current);
      sc.dispose();
    };
  }, [handleResize]);

  /* ── Apply telemetry to scene whenever it changes ────────────────────────── */
  useEffect(() => {
    applyTelemetry(telemetry);
  }, [telemetry, applyTelemetry]);

  /* ── Live data subscription ──────────────────────────────────────────────── */
  useEffect(() => {
    let es: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const parseTelemetry = (raw: Record<string, unknown>): TelemetryState => ({
      cpu_usage:           Number(raw.cpu_usage           ?? DEFAULT_TELEMETRY.cpu_usage),
      cpu_temperature:     Number(raw.cpu_temperature      ?? DEFAULT_TELEMETRY.cpu_temperature),
      gpu_usage:           Number(raw.gpu_usage            ?? DEFAULT_TELEMETRY.gpu_usage),
      gpu_temperature:     Number(raw.gpu_temperature      ?? DEFAULT_TELEMETRY.gpu_temperature),
      memory_usage:        Number(raw.memory_usage         ?? DEFAULT_TELEMETRY.memory_usage),
      battery_level:       Number(raw.battery_level        ?? DEFAULT_TELEMETRY.battery_level),
      battery_health:      Number(raw.battery_health       ?? DEFAULT_TELEMETRY.battery_health),
      battery_temperature: Number(raw.battery_temperature  ?? DEFAULT_TELEMETRY.battery_temperature),
      disk_usage:          Number(raw.disk_usage           ?? DEFAULT_TELEMETRY.disk_usage),
      fan_speed:           Number(raw.fan_speed            ?? DEFAULT_TELEMETRY.fan_speed),
      signal_strength_dbm: Number(raw.signal_strength_dbm  ?? DEFAULT_TELEMETRY.signal_strength_dbm),
      power_source:        String(raw.power_source         ?? DEFAULT_TELEMETRY.power_source),
      thermal_state:       String(raw.thermal_state        ?? DEFAULT_TELEMETRY.thermal_state),
      device_id:           String(raw.device_id            ?? DEFAULT_TELEMETRY.device_id),
      source:              String(raw.source               ?? DEFAULT_TELEMETRY.source),
      timestamp:           String(raw.timestamp            ?? new Date().toISOString()),
    });

    // SSE path
    function connectSSE() {
      es = new EventSource(`${API}/live-stream/sse`);
      es.addEventListener('connected', () => setSseConnected(true));
      es.addEventListener('telemetry_tick', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          setTelemetry(parseTelemetry(data));
          setLastUpdate(new Date().toLocaleTimeString());
        } catch { /* malformed */ }
      });
      es.onerror = () => {
        setSseConnected(false);
        es?.close();
        setTimeout(connectSSE, 5000);
      };
    }

    // REST fallback: poll latest telemetry every 3 s
    async function pollLatest() {
      try {
        const res = await fetch(`${API}/telemetry/?limit=1&sort_desc=true`);
        if (!res.ok) return;
        const rows = await res.json();
        if (Array.isArray(rows) && rows.length > 0) {
          setTelemetry(parseTelemetry(rows[0]));
          setLastUpdate(new Date().toLocaleTimeString());
        }
      } catch { /* silently ignore */ }
    }

    connectSSE();
    pollLatest();
    pollTimer = setInterval(pollLatest, 3000);

    return () => {
      es?.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, []);

  // ── UI helpers ──────────────────────────────────────────────────────────────
  const healthColor = (score: number) =>
    score > 75 ? '#10b981' : score > 50 ? '#f59e0b' : '#ef4444';

  const healthScore = Math.round(
    100 -
    (telemetry.cpu_usage * 0.3) -
    ((telemetry.cpu_temperature - 30) / 70 * 25) -
    (Math.max(0, 20 - telemetry.battery_level) * 0.5)
  );

  const ZONE_LABELS = [
    { name: 'CPU',     temp: telemetry.cpu_temperature,              usage: telemetry.cpu_usage,     unit: '°C' },
    { name: 'GPU',     temp: telemetry.gpu_temperature,              usage: telemetry.gpu_usage,     unit: '°C' },
    { name: 'Battery', temp: telemetry.battery_temperature,          usage: 100 - telemetry.battery_level, unit: '°C' },
    { name: 'RAM',     temp: telemetry.cpu_temperature * 0.75,       usage: telemetry.memory_usage,  unit: '°C' },
    { name: 'SSD',     temp: telemetry.cpu_temperature * 0.7,        usage: telemetry.disk_usage,    unit: '°C' },
    { name: 'Exhaust', temp: telemetry.cpu_temperature * 1.08,       usage: Math.max(telemetry.cpu_usage, telemetry.gpu_usage), unit: '°C' },
  ];

  return (
    <div
      id="digital-twin-3d-panel"
      style={{
        background:   'linear-gradient(135deg, #060b14 0%, #0f172a 100%)',
        borderRadius: 16,
        border:       '1px solid #1e3a5f',
        overflow:     'hidden',
        fontFamily:   '"Inter", "SF Pro Display", system-ui, sans-serif',
        color:        '#e2e8f0',
      }}
    >
      {/* ── Header ── */}
      <div style={{
        padding:     '18px 22px 14px',
        borderBottom:'1px solid #1e293b',
        display:     'flex', alignItems: 'center', gap: 12,
        background:  'rgba(6,11,20,0.7)',
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: 'linear-gradient(135deg, #1d4ed8, #6366f1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
        }}>🖥️</div>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#f1f5f9' }}>
            3D Digital Twin
          </h2>
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#475569' }}>
            Phase 48 · Live Three.js Visualization · {telemetry.device_id}
          </p>
        </div>

        {/* SSE indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: sseConnected ? '#10b981' : '#f59e0b',
            display: 'inline-block',
            boxShadow: sseConnected ? '0 0 6px #10b98188' : 'none',
            animation: sseConnected ? 'twin-pulse 1.8s infinite' : 'none',
          }} />
          <span
            suppressHydrationWarning
            style={{ fontSize: '0.72rem', color: sseConnected ? '#10b981' : '#f59e0b' }}
          >
            {mounted ? (sseConnected ? 'LIVE' : 'POLLING') : 'POLLING'} · {mounted ? lastUpdate : '—'}
          </span>
        </div>

        {/* View preset buttons */}
        <div style={{ display: 'flex', gap: 6 }}>
          {(['free', 'top', 'side'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              style={{
                background:  viewMode === v ? '#6366f1' : '#1e293b',
                border:     `1px solid ${viewMode === v ? '#6366f1' : '#334155'}`,
                borderRadius: 8,
                color:       viewMode === v ? '#ffffff' : '#64748b',
                fontSize:   '0.7rem', fontWeight: 600, padding: '5px 10px',
                cursor:     'pointer', textTransform: 'uppercase',
                transition: 'all 0.2s',
              }}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* ── Main layout: canvas + side panel ── */}
      <div style={{ display: 'flex', height: '520px' }}>

        {/* Three.js canvas */}
        <div style={{ flex: 1, position: 'relative' }}>
          <canvas
            ref={canvasRef}
            onClick={handleCanvasClick}
            style={{ width: '100%', height: '100%', display: 'block', cursor: 'grab' }}
          />

          {/* Zone click tooltip */}
          {hoveredZone && (
            <div style={{
              position:   'absolute',
              left:       hoveredZone.x + 12,
              top:        hoveredZone.y - 12,
              background: 'rgba(15,23,42,0.95)',
              border:     '1px solid #6366f1',
              borderRadius: 10,
              padding:    '10px 14px',
              pointerEvents: 'none',
              backdropFilter: 'blur(8px)',
              zIndex:     10,
            }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#a5b4fc', marginBottom: 4 }}>
                {hoveredZone.name}
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#f1f5f9' }}>
                {hoveredZone.value}{hoveredZone.unit}
              </div>
              <div style={{ fontSize: '0.65rem', color: '#475569', marginTop: 2 }}>
                {hoveredZone.metric}
              </div>
            </div>
          )}

          {/* Canvas overlay: interaction hint */}
          <div style={{
            position: 'absolute', bottom: 10, left: '50%', transform: 'translateX(-50%)',
            fontSize: '0.65rem', color: '#334155', pointerEvents: 'none',
            background: 'rgba(6,11,20,0.7)', padding: '4px 10px', borderRadius: 9999,
          }}>
            drag to rotate · scroll to zoom · click zones for details
          </div>
        </div>

        {/* ── Side telemetry panel ── */}
        <div style={{
          width:        '230px',
          borderLeft:   '1px solid #1e293b',
          padding:      '16px 14px',
          overflowY:    'auto',
          display:      'flex',
          flexDirection:'column',
          gap:          12,
          background:   'rgba(6,11,20,0.6)',
        }}>

          {/* Health score */}
          <div style={{
            background:   '#0f172a',
            borderRadius: 10,
            padding:      '12px',
            border:       `1px solid ${healthColor(healthScore)}44`,
            textAlign:    'center',
          }}>
            <div style={{ fontSize: '2rem', fontWeight: 900, color: healthColor(healthScore) }}>
              {healthScore}
            </div>
            <div style={{ fontSize: '0.65rem', color: '#64748b' }}>HEALTH SCORE</div>
            <div style={{ marginTop: 6, height: 4, background: '#1e293b', borderRadius: 2 }}>
              <div style={{
                width:        `${Math.max(0, Math.min(100, healthScore))}%`,
                height:       '100%',
                borderRadius: 2,
                background:   `linear-gradient(90deg, ${healthColor(healthScore)}88, ${healthColor(healthScore)})`,
                transition:   'width 0.6s ease',
              }} />
            </div>
          </div>

          {/* Heat zone table */}
          <div>
            <div style={{ fontSize: '0.65rem', color: '#475569', fontWeight: 600, marginBottom: 6 }}>
              TEMPERATURE ZONES
            </div>
            {ZONE_LABELS.map(z => {
              const col = tempToColor(z.temp).getHexString();
              return (
                <div key={z.name} style={{
                  display:       'flex',
                  alignItems:    'center',
                  gap:           8,
                  marginBottom:  5,
                }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: 2,
                    background: `#${col}`,
                    boxShadow:  `0 0 4px #${col}88`,
                    flexShrink: 0,
                  }} />
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8', flex: 1 }}>{z.name}</div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: `#${col}` }}>
                    {Math.round(z.temp)}°C
                  </div>
                </div>
              );
            })}
          </div>

          {/* Battery status */}
          <div style={{
            background: '#0f172a', borderRadius: 10, padding: '10px 12px',
            border: `1px solid ${batteryColor(telemetry.battery_level).getHexString() === 'ef4444' ? '#ef444433' : '#10b98133'}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: '0.65rem', color: '#475569' }}>BATTERY</span>
              <span style={{ fontSize: '0.65rem', color: telemetry.power_source === 'ac' ? '#10b981' : '#f59e0b' }}>
                {telemetry.power_source === 'ac' ? '⚡ AC' : '🔋 BAT'}
              </span>
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: `#${batteryColor(telemetry.battery_level).getHexString()}` }}>
              {Math.round(telemetry.battery_level)}%
            </div>
            <div style={{ height: 4, background: '#1e293b', borderRadius: 2, marginTop: 6 }}>
              <div style={{
                width:        `${telemetry.battery_level}%`,
                height:       '100%',
                borderRadius: 2,
                background:   `#${batteryColor(telemetry.battery_level).getHexString()}`,
                transition:   'width 0.6s ease',
              }} />
            </div>
            <div style={{ fontSize: '0.65rem', color: '#475569', marginTop: 4 }}>
              Health {telemetry.battery_health}% · {Math.round(telemetry.battery_temperature)}°C
            </div>
          </div>

          {/* CPU state */}
          <div style={{
            background: '#0f172a', borderRadius: 10, padding: '10px 12px',
            border: '1px solid #6366f133',
          }}>
            <div style={{ fontSize: '0.65rem', color: '#475569', marginBottom: 6 }}>CPU STATE</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <div style={{
                fontSize: '1.3rem', fontWeight: 800,
                color: `#${tempToColor(telemetry.cpu_temperature).getHexString()}`,
              }}>
                {Math.round(telemetry.cpu_usage)}%
              </div>
              <div>
                <div style={{ fontSize: '0.65rem', color: '#64748b' }}>Usage</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                  {Math.round(telemetry.cpu_temperature)}°C
                </div>
              </div>
            </div>
            <div style={{ height: 4, background: '#1e293b', borderRadius: 2, marginBottom: 8 }}>
              <div style={{
                width:        `${telemetry.cpu_usage}%`,
                height:       '100%',
                borderRadius: 2,
                background:   `#${tempToColor(telemetry.cpu_temperature).getHexString()}`,
                transition:   'width 0.3s ease',
              }} />
            </div>

            {/* Fan + Memory */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {[
                { label: 'Fan',    value: `${Math.round(telemetry.fan_speed)} RPM` },
                { label: 'RAM',    value: `${Math.round(telemetry.memory_usage)}%` },
                { label: 'GPU',    value: `${Math.round(telemetry.gpu_usage)}%`    },
                { label: 'Disk',   value: `${Math.round(telemetry.disk_usage)}%`   },
                { label: 'WiFi',   value: `${telemetry.signal_strength_dbm} dBm`   },
                { label: 'State',  value: telemetry.thermal_state                  },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div style={{ fontSize: '0.6rem', color: '#475569' }}>{label}</div>
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8', fontWeight: 600 }}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Source */}
          <div
            suppressHydrationWarning
            style={{ fontSize: '0.65rem', color: '#334155', textAlign: 'center', marginTop: 'auto' }}
          >
            {telemetry.source} · {mounted ? new Date(telemetry.timestamp).toLocaleTimeString() : '—'}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes twin-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(1.4); }
        }
      `}</style>
    </div>
  );
};

export default DigitalTwin3D;
