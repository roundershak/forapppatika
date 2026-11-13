// "Sıfırdan Ev Yapıyoruz" — deterministic Three.js scene.
// window.renderAt(t) draws the frame at time t (seconds) and returns a JPEG data URL.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';

const params = new URLSearchParams(location.search);
const W = +(params.get('w') || 1080), H = +(params.get('h') || 1920);

// ---------- math helpers ----------
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const lerp = (a, b, p) => a + (b - a) * p;
const prog = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
const E = {
  lin: x => x,
  io: x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  out: x => 1 - Math.pow(1 - x, 3),
  in: x => x * x * x,
  back: x => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
  bounce: x => {
    const n1 = 7.5625, d1 = 2.75;
    if (x < 1 / d1) return n1 * x * x;
    if (x < 2 / d1) return n1 * (x -= 1.5 / d1) * x + 0.75;
    if (x < 2.5 / d1) return n1 * (x -= 2.25 / d1) * x + 0.9375;
    return n1 * (x -= 2.625 / d1) * x + 0.984375;
  },
  elastic: x => (x === 0 || x === 1) ? x : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * (2 * Math.PI) / 3) + 1,
};
const lerpV = (a, b, p) => Array.isArray(a) ? a.map((v, i) => lerp(v, b[i], p)) : lerp(a, b, p);
// keyframes: [[time, value, easeFn?], ...] — ease belongs to the segment ending at that key
function kf(t, keys) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, v0] = keys[i], [t1, v1, e] = keys[i + 1];
    if (t <= t1) return lerpV(v0, v1, (e || E.io)((t - t0) / (t1 - t0)));
  }
  return keys[keys.length - 1][1];
}
function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const hash = i => { let x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

// ---------- renderer / scene ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const SKY_CLEAR = new THREE.Color(0xC3DBEF), SKY_COLD = new THREE.Color(0xB9CCDD), SKY_RAIN = new THREE.Color(0x98A9BA);
scene.background = SKY_CLEAR.clone();
scene.fog = new THREE.Fog(SKY_CLEAR.clone(), 16, 34);
const camera = new THREE.PerspectiveCamera(46, W / H, 0.1, 100);

const hemi = new THREE.HemisphereLight(0xffffff, 0xd8cbb8, 1.55);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff4e6, 2.3);
sun.position.set(6, 11, 8);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 40 });
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.02;
sun.shadow.radius = 4;
scene.add(sun);

// ---------- materials & textures ----------
const M = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.78, metalness: 0, ...o });
const RB = (w, h, d, r = 0.05, s = 3) => new RoundedBoxGeometry(w, h, d, s, r);
function mesh(geo, mat, parent, shadow = true) {
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = shadow; m.receiveShadow = true;
  if (parent) parent.add(m);
  return m;
}
function canvasTex(size, draw, repeat = [1, 1]) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d'); draw(g, size);
  const tx = new THREE.CanvasTexture(c);
  tx.colorSpace = THREE.SRGBColorSpace; tx.wrapS = tx.wrapT = THREE.RepeatWrapping; tx.repeat.set(...repeat);
  tx.anisotropy = 4;
  return tx;
}
const rnd = mulberry32(7);
const cardboardTex = canvasTex(256, (g, s) => {
  g.fillStyle = '#C99F68'; g.fillRect(0, 0, s, s);
  for (let x = 0; x < s; x += 10) { g.fillStyle = 'rgba(120,80,40,0.18)'; g.fillRect(x, 0, 3, s); }
  g.fillStyle = '#E6D2A6'; g.fillRect(0, s * 0.44, s, s * 0.12); // tape
  g.fillStyle = 'rgba(90,60,30,0.5)'; g.font = 'bold 26px sans-serif'; g.fillText('⬆ ⬆', s * 0.62, s * 0.3);
});
const woodTex = canvasTex(256, (g, s) => {
  g.fillStyle = '#FFFFFF'; g.fillRect(0, 0, s, s);
  for (let y = 0; y < s; y += 32) {
    g.fillStyle = 'rgba(90,50,20,0.28)'; g.fillRect(0, y, s, 3);
    for (let k = 0; k < 6; k++) { g.fillStyle = 'rgba(110,70,30,0.10)'; g.fillRect(0, y + 6 + rnd() * 22, s, 1.5); }
  }
}, [1, 1]);
const groundTex = canvasTex(512, (g, s) => {
  g.fillStyle = '#E2E2DE'; g.fillRect(0, 0, s, s);
  g.strokeStyle = 'rgba(120,120,115,0.22)'; g.lineWidth = 3;
  for (let i = 0; i <= s; i += 128) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i, s); g.stroke(); g.beginPath(); g.moveTo(0, i); g.lineTo(s, i); g.stroke(); }
}, [10, 4]);

const COL = {
  blue: 0xA9C7E3, cream: 0xF3E6CF, gray: 0xD5D8DC, orange: 0xF29E4C, brown: 0x9C6B43,
  skin: 0xF6D5B5, sweater: 0x9CC7EA, pants: 0x8A7563, dark: 0x2B2B33,
};

// ---------- world: street & city ----------
const world = new THREE.Group(); scene.add(world);
const ground = mesh(new THREE.PlaneGeometry(90, 90), M(0xCFD3D6), world, false);
ground.rotation.x = -Math.PI / 2;
const sidewalk = mesh(new THREE.BoxGeometry(60, 0.08, 7.2), M(0xffffff, { map: groundTex }), world, false);
sidewalk.position.set(0, 0.04, -0.6);
const curb = mesh(RB(60, 0.14, 0.3, 0.04), M(0xC9C9C4), world);
curb.position.set(0, 0.07, 3.05);
const road = mesh(new THREE.BoxGeometry(60, 0.02, 8), M(0x9DA3AA), world, false);
road.position.set(0, 0.01, 7.2);
for (let x = -28; x < 28; x += 3) { const d = mesh(new THREE.BoxGeometry(1.4, 0.03, 0.16), M(0xF4F1EA), world, false); d.position.set(x, 0.025, 6.8); }
const lot = mesh(RB(4.6, 0.06, 3.6, 0.03), M(0xCDB592), world, false); // construction lot
lot.position.set(0, 0.08, 0.2);

const buildingPal = [0xA9C7E3, 0xF3E6CF, 0xD5D8DC, 0xE8CDB0, 0xBCD2E8, 0xEADFCF];
const winGeo = RB(0.34, 0.44, 0.06, 0.04, 2);
const winMat = M(0xF6F8FB, { roughness: 0.4 });
const winList = [];
function building(x, z, w, h, d, color) {
  const b = mesh(RB(w, h, d, 0.12), M(color), world);
  b.position.set(x, h / 2, z);
  const top = mesh(RB(w + 0.1, 0.18, d + 0.1, 0.06), M(new THREE.Color(color).multiplyScalar(0.88)), world);
  top.position.set(x, h + 0.05, z);
  const cols = Math.max(1, Math.floor((w - 0.4) / 0.62)), rows = Math.floor((h - 0.8) / 0.9);
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    winList.push([x - (cols - 1) * 0.31 + c * 0.62, 0.9 + r * 0.9, z + d / 2 + 0.01]);
  }
}
{
  const r = mulberry32(42);
  for (let x = -16; x < 16;) { const w = 2 + r() * 1.4; building(x + w / 2, -5.6, w, 3 + r() * 3.5, 2.2, buildingPal[Math.floor(r() * buildingPal.length)]); x += w + 0.25 + r() * 0.5; }
  for (let x = -18; x < 18;) { const w = 2.2 + r() * 1.6; building(x + w / 2, -9.5, w, 6 + r() * 5, 2.4, buildingPal[Math.floor(r() * buildingPal.length)]); x += w + 0.3; }
  const im = new THREE.InstancedMesh(winGeo, winMat, winList.length);
  const m4 = new THREE.Matrix4();
  winList.forEach((p, i) => { m4.makeTranslation(...p); im.setMatrixAt(i, m4); im.setColorAt(i, new THREE.Color(hash(i) > 0.75 ? 0xFBE3B8 : 0xF2F6FA)); });
  im.receiveShadow = true; world.add(im);
}
function lamp(x, z) {
  const p = mesh(new THREE.CylinderGeometry(0.06, 0.08, 3.4, 12), M(0x8D949C), world); p.position.set(x, 1.7, z);
  const arm = mesh(RB(0.7, 0.08, 0.08, 0.03), M(0x8D949C), world); arm.position.set(x + 0.3, 3.35, z);
  const head = mesh(RB(0.36, 0.16, 0.24, 0.05), M(COL.orange, { emissive: 0xF29E4C, emissiveIntensity: 0.25 }), world); head.position.set(x + 0.6, 3.26, z);
}
lamp(-4.6, 2.6); lamp(4.8, 2.6);

// ---------- character ----------
function makeChar() {
  const root = new THREE.Group(); scene.add(root);
  const body = new THREE.Group(); root.add(body); // squash/jitter container
  const sweater = M(COL.sweater), pants = M(COL.pants), skin = M(COL.skin), dark = M(COL.dark, { roughness: 0.4 });
  const legs = [];
  for (const s of [-1, 1]) {
    const hip = new THREE.Group(); hip.position.set(0.14 * s, 0.52, 0); body.add(hip);
    const leg = mesh(new THREE.CylinderGeometry(0.095, 0.1, 0.44, 16), pants, hip); leg.position.y = -0.22;
    const foot = mesh(RB(0.2, 0.1, 0.3, 0.045), M(0x5D4A3C), hip); foot.position.set(0, -0.46, 0.05);
    legs.push(hip);
  }
  const torso = mesh(new THREE.CylinderGeometry(0.29, 0.33, 0.72, 28), sweater, body); torso.position.y = 0.86;
  const belly = mesh(RB(0.3, 0.12, 0.05, 0.02), M(0xC4DFF3), body); belly.position.set(0, 0.78, 0.31);
  const scarf = mesh(new THREE.TorusGeometry(0.27, 0.075, 12, 28), M(COL.orange), body); scarf.position.y = 1.2; scarf.rotation.x = Math.PI / 2;
  const tail = mesh(RB(0.12, 0.3, 0.06, 0.03), M(COL.orange), body); tail.position.set(0.17, 1.06, 0.28); tail.rotation.z = 0.15;
  const arms = [];
  for (const s of [-1, 1]) {
    const sh = new THREE.Group(); sh.position.set(0.36 * s, 1.1, 0); body.add(sh);
    const arm = mesh(new THREE.CylinderGeometry(0.072, 0.072, 0.42, 14), sweater, sh); arm.position.y = -0.2;
    const hand = mesh(new THREE.SphereGeometry(0.088, 18, 14), skin, sh); hand.position.y = -0.44;
    arms.push(sh);
  }
  const head = new THREE.Group(); head.position.y = 1.24; body.add(head);
  const skull = mesh(RB(0.62, 0.56, 0.54, 0.16, 5), skin, head); skull.position.y = 0.28;
  const hat = mesh(RB(0.66, 0.2, 0.58, 0.08), M(COL.orange), head); hat.position.y = 0.6;
  const hatBand = mesh(RB(0.68, 0.08, 0.6, 0.04), M(0xE08A3A), head); hatBand.position.y = 0.5;
  const pom = mesh(new THREE.SphereGeometry(0.08, 16, 12), M(COL.cream), head); pom.position.y = 0.74;
  const face = new THREE.Group(); face.position.set(0, 0.28, 0.272); head.add(face);
  const eyeGeo = new THREE.SphereGeometry(0.052, 18, 14);
  const eyes = [], arcs = [], brows = [];
  for (const s of [-1, 1]) {
    const e = mesh(eyeGeo, dark, face, false); e.position.set(0.125 * s, 0.03, 0); e.scale.z = 0.5;
    const hl = mesh(new THREE.SphereGeometry(0.016, 8, 8), M(0xffffff, { emissive: 0xffffff, emissiveIntensity: 0.6 }), e, false); hl.position.set(0.018, 0.02, 0.04);
    eyes.push(e);
    const a = mesh(new THREE.TorusGeometry(0.045, 0.014, 6, 16, Math.PI), dark, face, false); a.position.set(0.125 * s, 0.02, 0.01); a.visible = false;
    arcs.push(a);
    const b = mesh(RB(0.11, 0.022, 0.02, 0.01, 2), M(0x6B4A33), face, false); b.position.set(0.125 * s, 0.12, 0.005);
    brows.push(b);
  }
  const cheeks = [-1, 1].map(s => { const c = mesh(new THREE.CircleGeometry(0.045, 18), M(0xF4A9A0, { transparent: true, opacity: 0.7 }), face, false); c.position.set(0.2 * s, -0.06, 0.006); return c; });
  const mouth = new THREE.Group(); mouth.position.set(0, -0.1, 0.008); face.add(mouth);
  const mSmile = mesh(new THREE.TorusGeometry(0.065, 0.016, 8, 20, Math.PI), dark, mouth, false); mSmile.rotation.z = Math.PI;
  const mGrin = mesh(new THREE.CircleGeometry(0.08, 24, Math.PI, Math.PI), M(0x7A2E2E), mouth, false); mGrin.position.y = 0.025;
  const mO = mesh(new THREE.TorusGeometry(0.04, 0.016, 8, 20), dark, mouth, false); mO.scale.y = 1.25;
  const mFlat = mesh(RB(0.12, 0.024, 0.02, 0.01, 2), dark, mouth, false);
  const mFrown = mesh(new THREE.TorusGeometry(0.06, 0.016, 8, 20, Math.PI), dark, mouth, false); mFrown.position.y = -0.04;
  return { root, body, legs, arms, head, eyes, arcs, brows, cheeks, mouth, m: { smile: mSmile, grin: mGrin, o: mO, flat: mFlat, frown: mFrown } };
}
const ch = makeChar();

// ---------- house ----------
const house = new THREE.Group(); scene.add(house);
const P = 0.36, WALL_T = 0.2, ROWS = 6;
const pillarMat = M(COL.cream);
const pillars = [0, 1, 2, 3].map(() => mesh(RB(P, 1, P, 0.05), pillarMat, house));
const floor = mesh(RB(1, 0.05, 1, 0.02), M(0xD9A56B, { map: woodTex }), house, false);
const brickGeo = RB(1, 1, 1, 0.035, 2);
const bricks = new THREE.InstancedMesh(brickGeo, M(0xffffff, { roughness: 0.9 }), 400);
bricks.castShadow = bricks.receiveShadow = true; house.add(bricks);
const brickPal = [0xD3D8DE, 0xC6CDD5, 0xDEDBD3, 0xCBD3DC];
for (let i = 0; i < 400; i++) bricks.setColorAt(i, new THREE.Color(brickPal[Math.floor(hash(i + 3) * brickPal.length)]));
// static brick order: row-major across walls
const WALLS = [
  { k: 'front', cols: 9 }, { k: 'right', cols: 6 }, { k: 'back', cols: 9 }, { k: 'left', cols: 6 },
];
const brickOrder = [];
for (let r = 0; r < ROWS; r++) for (let w = 0; w < 4; w++) for (let c = 0; c < WALLS[w].cols; c++) {
  if (w === 0 && c >= 3 && c <= 5 && r <= 4) continue; // door opening
  brickOrder.push([r, w, c]);
}
// cardboard roof (scene 2)
const cardMat = M(0xffffff, { map: cardboardTex });
const card = new THREE.Group(); house.add(card);
const cardHalves = [-1, 1].map(s => {
  const pivot = new THREE.Group(); pivot.position.x = 0.8 * s; card.add(pivot);
  const half = mesh(new THREE.BoxGeometry(0.82, 0.035, 1.34), cardMat, pivot); half.position.x = -0.41 * s;
  return pivot;
});
// gable roof
const roofMat = M(0xE79A5A, { map: woodTex });
const roof = new THREE.Group(); house.add(roof);
const slabGeo = RB(1, 0.1, 1, 0.04);
const slabs = [0, 1].map(() => mesh(slabGeo, roofMat, roof));
const triShape = new THREE.Shape(); triShape.moveTo(-0.5, 0); triShape.lineTo(0.5, 0); triShape.lineTo(0, 1); triShape.closePath();
const triGeo = new THREE.ExtrudeGeometry(triShape, { depth: 0.08, bevelEnabled: false });
const gables = [0, 1].map(() => mesh(triGeo, M(COL.cream), roof));
const ridge = mesh(new THREE.CylinderGeometry(0.07, 0.07, 1, 14), M(COL.orange), roof); ridge.rotation.x = Math.PI / 2;
// door
const doorHinge = new THREE.Group(); house.add(doorHinge);
const doorPanel = mesh(RB(1, 1, 0.08, 0.04), M(0xB07A4C, { map: woodTex }), doorHinge);
const knob = mesh(new THREE.SphereGeometry(0.05, 14, 10), M(COL.orange, { metalness: 0.3, roughness: 0.4 }), doorHinge);
const doorLamp = mesh(new THREE.SphereGeometry(0.09, 16, 12), M(0xFFF1CF, { emissive: 0xFFC766, emissiveIntensity: 0 }), house);
// windows
const glassMat = M(0xBFE0F5, { roughness: 0.15, emissive: 0xFFC766, emissiveIntensity: 0 });
const windows = [-1, 1].map(s => {
  const g = new THREE.Group(); house.add(g);
  mesh(RB(0.74, 0.74, 0.07, 0.04), M(0xFAF7F0), g);
  const gl = mesh(RB(0.6, 0.6, 0.05, 0.02), glassMat, g); gl.position.z = 0.02;
  const v = mesh(RB(0.05, 0.6, 0.07), M(0xFAF7F0), g); v.position.z = 0.02;
  const h = mesh(RB(0.6, 0.05, 0.07), M(0xFAF7F0), g); h.position.z = 0.02;
  const sill = mesh(RB(0.86, 0.07, 0.16, 0.03), M(COL.orange), g); sill.position.set(0, -0.4, 0.04);
  return g;
});
const puddle = mesh(new THREE.CylinderGeometry(1, 1, 0.02, 40), M(0x86B9DE, { roughness: 0.1, transparent: true, opacity: 0.85 }), house, false);
const interiorLight = new THREE.PointLight(0xFFC77A, 0, 6, 1.5); house.add(interiorLight);

// ---------- props: rain, wind flakes, stars, ! ? ----------
const RAIN_N = 1100;
const rainMat = new THREE.MeshBasicMaterial({ color: 0xE3EEF8, transparent: true, opacity: 0.7 });
const rain = new THREE.InstancedMesh(new THREE.BoxGeometry(0.014, 0.26, 0.014), rainMat, RAIN_N);
rain.frustumCulled = false; scene.add(rain);
const FLAKE_N = 80;
const flakes = new THREE.InstancedMesh(new THREE.SphereGeometry(0.025, 6, 6), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9 }), FLAKE_N);
flakes.frustumCulled = false; scene.add(flakes);
const starShape = new THREE.Shape();
for (let i = 0; i < 10; i++) { const a = Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 0.045 : 0.1; const x = Math.cos(a) * r, y = Math.sin(a) * r; i ? starShape.lineTo(x, y) : starShape.moveTo(x, y); }
const starGeo = new THREE.ExtrudeGeometry(starShape, { depth: 0.03, bevelEnabled: false });
const stars = [0, 1, 2].map(() => mesh(starGeo, M(0xFFD166, { emissive: 0xFFC233, emissiveIntensity: 0.4 }), scene, false));
let bang = null, quest = null;
async function loadFont() {
  const json = await (await fetch('/node_modules/three/examples/fonts/helvetiker_bold.typeface.json')).json();
  const font = new FontLoader().parse(json);
  const mk = s => { const g = new TextGeometry(s, { font, size: 0.42, depth: 0.1, curveSegments: 6, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.015, bevelSegments: 2 }); g.center(); const m = mesh(g, M(COL.orange, { emissive: 0xF29E4C, emissiveIntensity: 0.25 }), scene, false); m.visible = false; return m; };
  bang = mk('!'); quest = mk('?');
}

// =====================================================================
// TIMELINE
// =====================================================================
const houseW = t => kf(t, [[0, 1.4], [16.3, 1.4], [17.2, 3.0, E.back]]);
const houseD = t => kf(t, [[0, 1.1], [16.3, 1.1], [17.2, 2.4, E.back]]);
const houseH = t => kf(t, [[0, 0.5], [8.3, 0.5], [8.75, 1.0, E.back], [16.3, 1.0], [17.2, 2.6, E.back]]);
const roofW = t => kf(t, [[0, 1.75], [20.3, 1.75], [21.0, 3.45, E.back]]);
const roofD = t => kf(t, [[0, 1.45], [20.3, 1.45], [21.0, 2.85, E.back]]);
const roofRise = w => 0.32 * w + 0.12;

function rainAmount(t) {
  return Math.max(
    prog(t, 6.0, 6.5) * (1 - prog(t, 8.0, 8.5)),
    prog(t, 17.25, 17.7) * (1 - prog(t, 20.5, 21.0)),
    0.65 * prog(t, 28.25, 28.8));
}

// character position (x,z)
function charXZ(t) {
  if (t >= 16.3 && t < 17.2) return [houseW(t) / 2 + 0.45, 0.3];
  return kf(t, [
    [0, [-3.6, 1.9]], [2.4, [-1.1, 1.9], E.lin], [4.0, [-1.1, 1.9]], [4.35, [-1.2, 1.0], E.io],
    [7.15, [-1.2, 1.0]], [7.4, [-1.45, 1.15], E.out], [8.0, [-1.2, 1.0]],
    [12.0, [-1.2, 1.0]], [12.4, [0, 1.6], E.io], [12.5, [0, 1.6]], [12.65, [0, 0.92], E.in], [12.95, [0, 1.35], E.out],
    [13.45, [0, 1.35]], [13.68, [0, 0.92], E.in], [14.0, [0, 1.45], E.out],
    [16.0, [0, 1.45]], [16.3, [1.15, 0.3], E.io],
    [17.2, [1.95, 0.3]], [17.6, [1.95, 1.75], E.out],
    [21.0, [1.95, 1.75]], [21.6, [1.25, 2.15], E.io], [22.55, [1.25, 2.15]], [22.85, [1.05, 1.75], E.io],
    [23.45, [1.05, 1.75]], [23.85, [0.85, 2.35], E.io],
    [24.6, [0.85, 2.35]], [25.3, [0, 2.05], E.io], [27.45, [0, 2.05]], [28.05, [0, 0.4], E.lin],
  ]);
}
function charYaw(t) {
  return kf(t, [
    [0, 0.8], [2.35, 0.8], [2.6, 0.0], [4.0, 0.0], [4.12, -2.9, E.lin], [4.35, -2.9], [4.55, 0.9],
    [6.3, 0.9], [6.5, 0.45], [7.15, 0.45], [7.3, 0.15], [8.2, 0.15], [8.4, 0.9], [10.7, 0.9], [10.9, 0.3],
    [12.0, 0.3], [12.15, 1.05], [12.35, 1.05], [12.5, Math.PI], [14.05, Math.PI], [14.35, 0.75],
    [16.0, 0.75], [16.15, 1.6], [16.3, 1.6], [16.4, -Math.PI / 2],
    [17.3, -Math.PI / 2], [17.6, -0.9], [21.0, -0.9], [21.15, -0.65], [21.55, -0.65], [21.7, -2.5],
    [22.55, -2.5], [22.75, -Math.PI], [23.45, -Math.PI], [23.85, -0.15],
    [24.6, -0.15], [24.75, -1.9], [25.2, -1.9], [25.35, -Math.PI], [25.8, -Math.PI], [26.0, 0.0],
    [27.2, 0.0], [27.4, -Math.PI],
  ]);
}
// expression timeline
const EXPR = [
  [0, 'cold'], [2.4, 'idea'], [4.0, 'focus'], [5.45, 'happy'], [6.3, 'worried'], [7.15, 'shock'],
  [8.3, 'focus'], [10.7, 'proud'], [12.0, 'happy'], [12.65, 'dizzy'], [13.3, 'focus'], [13.68, 'dizzy'],
  [14.3, 'confused'], [16.0, 'effort'], [17.3, 'shock'], [18.3, 'oops'], [20.0, 'effort'], [21.0, 'focus'],
  [23.4, 'happy'],
];
// pose segments [start, end, name]
const POSES = [
  [0, 2.55, 'cold'], [2.55, 3.95, 'idea'], [4.35, 5.25, 'place'], [5.45, 6.1, 'cheer'], [6.3, 7.1, 'lookup'],
  [7.1, 8.1, 'shock'], [8.45, 10.65, 'hammer'], [10.7, 12.0, 'proud'], [12.65, 13.3, 'dizzy'], [13.3, 13.7, 'crouch'],
  [13.7, 14.3, 'dizzy'], [14.45, 15.9, 'measure'], [16.3, 17.25, 'push'], [17.35, 18.35, 'lookup'],
  [18.35, 19.7, 'facepalm'], [20.1, 21.0, 'pull'], [21.6, 22.5, 'point'], [22.9, 23.35, 'tap'],
  [23.85, 24.6, 'present'], [26.0, 27.2, 'wave'],
];
function poseValues(name, t) {
  const p = { lx: 0, lz: 0, rx: 0, rz: 0, head: 0, crouch: 0 };
  switch (name) {
    case 'cold': { const w = Math.sin(t * 22) * 0.12; Object.assign(p, { lx: -1.25 + w, lz: 0.95, rx: -1.25 - w, rz: -0.95, head: 0.12 }); break; }
    case 'idea': Object.assign(p, { rx: -0.4, rz: 2.7 + Math.sin(t * 6) * 0.08, lz: -0.15, head: -0.08 }); break;
    case 'place': { const k = Math.sin(t * 9); Object.assign(p, { lx: -1.0 - 0.4 * k, rx: -1.0 + 0.4 * k, lz: 0.15, rz: -0.15, head: 0.2 }); break; }
    case 'cheer': Object.assign(p, { lz: -2.6, rz: 2.6, head: -0.15 }); break;
    case 'lookup': Object.assign(p, { lz: -0.25, rz: 0.25, head: -0.45 }); break;
    case 'shock': Object.assign(p, { lz: -1.9, rz: 1.9, lx: -0.3, rx: -0.3, head: -0.1 }); break;
    case 'hammer': { const k = Math.sin(t * 15); Object.assign(p, { rx: -1.8 + 0.7 * k, lx: -0.9, lz: 0.2, head: 0.18 }); break; }
    case 'proud': Object.assign(p, { lz: -0.55, rz: 0.55, lx: 0.25, rx: 0.25, head: -0.12 }); break;
    case 'dizzy': { const k = Math.sin(t * 12); Object.assign(p, { lz: -1.1 - 0.3 * k, rz: 1.1 - 0.3 * k, head: 0.12 * k }); break; }
    case 'crouch': Object.assign(p, { lx: -1.2, rx: -1.2, crouch: 1, head: -0.1 }); break;
    case 'measure': Object.assign(p, { rz: 2.85, rx: -0.2, lz: -0.6, head: -0.15 + Math.sin(t * 3) * 0.05 }); break;
    case 'push': Object.assign(p, { lx: -1.55, rx: -1.55, lz: 0.12, rz: -0.12, head: 0.1, crouch: 0.35 }); break;
    case 'facepalm': Object.assign(p, { rx: -2.45, rz: -0.55, head: 0.3 }); break;
    case 'pull': Object.assign(p, { lz: -2.8, rz: 2.8, lx: -0.3, rx: -0.3, head: -0.35 }); break;
    case 'point': Object.assign(p, { rx: -1.45, rz: 0.1, head: 0.0 }); break;
    case 'tap': { const k = Math.max(0, Math.sin((t - 22.9) * 14)); Object.assign(p, { rx: -1.5 - 0.15 * k, rz: -0.1 }); break; }
    case 'present': Object.assign(p, { lz: -1.1, rz: 1.1, lx: -0.35, rx: -0.35, head: -0.1 }); break;
    case 'wave': Object.assign(p, { rz: 2.55 + Math.sin(t * 13) * 0.35, rx: -0.2, head: -0.08 }); break;
  }
  return p;
}
function poseAt(t) {
  const acc = { lx: 0, lz: 0, rx: 0, rz: 0, head: 0, crouch: 0 }; let wsum = 0;
  for (const [s, e, n] of POSES) {
    if (t < s - 0.01 || t > e + 0.01) continue;
    const w = Math.min(E.io(prog(t, s, s + 0.16)), 1 - E.io(prog(t, e - 0.16, e)));
    if (w <= 0) continue;
    const v = poseValues(n, t);
    for (const k in acc) acc[k] += v[k] * w;
    wsum += w;
  }
  return { ...acc, w: Math.min(1, wsum) };
}
const BLINKS = [1.3, 4.6, 9.7, 11.5, 15.3, 19.1, 22.1, 24.2, 27.0];

function applyExpression(t) {
  let ex = 'focus';
  for (const [s, n] of EXPR) if (t >= s) ex = n;
  const m = ch.m;
  for (const k in m) m[k].visible = false;
  let eyeSY = 1, eyeS = 1, happyEyes = false, browL = 0, browR = 0, browY = 0.12;
  switch (ex) {
    case 'cold': m.flat.visible = true; eyeSY = 0.6; browL = -0.35; browR = 0.35; ch.mouth.scale.set(1, 1 + Math.sin(t * 40) * 0.6, 1); break;
    case 'idea': m.grin.visible = true; eyeS = 1.25; browY = 0.15; break;
    case 'focus': m.smile.visible = true; break;
    case 'happy': case 'proud': m.grin.visible = true; happyEyes = true; browY = 0.14; break;
    case 'worried': m.flat.visible = true; browL = -0.3; browR = 0.3; break;
    case 'shock': m.o.visible = true; eyeS = 1.35; browY = 0.16; break;
    case 'dizzy': m.o.visible = true; eyeSY = 0.35; browL = 0.3; browR = -0.3; break;
    case 'confused': m.flat.visible = true; browL = 0.0; browR = -0.35; browY = 0.13; break;
    case 'effort': m.flat.visible = true; eyeSY = 0.55; browL = 0.3; browR = -0.3; break;
    case 'oops': m.frown.visible = true; eyeSY = 0.7; browL = -0.4; browR = 0.4; break;
  }
  if (ex !== 'cold') ch.mouth.scale.set(1, 1, 1);
  const blink = BLINKS.some(b => t >= b && t < b + 0.12);
  ch.eyes.forEach((e, i) => { e.visible = !happyEyes; e.scale.set(eyeS, eyeS * (blink ? 0.1 : eyeSY), 0.5); });
  ch.arcs.forEach(a => { a.visible = happyEyes; });
  ch.brows[0].rotation.z = browL; ch.brows[1].rotation.z = browR;
  ch.brows.forEach(b => { b.position.y = browY; b.visible = !happyEyes || true; });
}

function updateChar(t) {
  const [x, z] = charXZ(t);
  const [x2, z2] = charXZ(t + 0.04);
  const speed = Math.hypot(x2 - x, z2 - z) / 0.04;
  const moving = clamp(speed / 1.2, 0, 1);
  ch.root.position.set(x, 0.08, z);
  ch.root.rotation.y = charYaw(t);
  ch.root.visible = t < 28.1;
  // walk cycle
  const ph = t * 13;
  ch.legs[0].rotation.x = Math.sin(ph) * 0.6 * moving;
  ch.legs[1].rotation.x = -Math.sin(ph) * 0.6 * moving;
  const pose = poseAt(t);
  const swing = Math.sin(ph) * 0.5 * moving * (1 - pose.w);
  ch.arms[0].rotation.set(pose.lx + swing, 0, pose.lz - 0.08 * (1 - pose.w));
  ch.arms[1].rotation.set(pose.rx - swing, 0, pose.rz + 0.08 * (1 - pose.w));
  ch.head.rotation.x = pose.head;
  // vertical: bob, jumps, crouch
  let y = Math.abs(Math.sin(ph)) * 0.05 * moving;
  const hop = (a, b, h) => (t > a && t < b ? Math.sin(Math.PI * (t - a) / (b - a)) * h : 0);
  y += hop(5.5, 5.78, 0.32) + hop(5.8, 6.08, 0.28) + hop(7.15, 7.42, 0.22) + hop(10.75, 10.98, 0.12) + hop(23.45, 23.7, 0.15) + hop(26.05, 26.3, 0.12);
  ch.root.position.y += y;
  // squash: crouch + bonk + landing
  const bonk = Math.max(1 - prog(t, 12.65, 12.85), 0) * (t >= 12.65 ? 1 : 0) + Math.max(1 - prog(t, 13.68, 13.88), 0) * (t >= 13.68 ? 1 : 0);
  const sq = 1 - pose.crouch * 0.18 - bonk * 0.12;
  ch.body.scale.set(1 + (1 - sq) * 0.6, sq, 1 + (1 - sq) * 0.6);
  // cold shiver
  const shiver = 1 - prog(t, 2.3, 2.6);
  ch.body.position.x = Math.sin(t * 57) * 0.018 * shiver;
  ch.body.rotation.z = Math.sin(t * 31) * 0.03 * shiver;
  applyExpression(t);
}

function updateHouse(t) {
  const Wd = houseW(t), Dd = houseD(t), Hh = houseH(t);
  // blocks/pillars
  const dropT = [4.35, 4.6, 4.85, 5.1];
  const corners = [[-1, 1], [1, 1], [1, -1], [-1, -1]];
  pillars.forEach((p, i) => {
    const d = E.bounce(prog(t, dropT[i], dropT[i] + 0.4));
    p.visible = t >= dropT[i];
    p.scale.set(1, Hh, 1);
    p.position.set(corners[i][0] * (Wd / 2 - P / 2), Hh / 2 + 0.11 + (1 - d) * 3, corners[i][1] * (Dd / 2 - P / 2));
  });
  // floor
  const fs = E.back(prog(t, 8.3, 8.6));
  floor.visible = t >= 8.3;
  floor.scale.set(Math.max(0.01, (Wd - 0.12) * fs), 1, Math.max(0.01, (Dd - 0.12) * fs));
  floor.position.set(0, 0.13, 0);
  // bricks
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), pos = new THREE.Vector3(), scl = new THREE.Vector3();
  let n = 0;
  const total = brickOrder.length;
  for (let j = 0; j < total; j++) {
    const appear = 9.0 + (j / total) * 1.55;
    if (t < appear) continue;
    const [r, w, c] = brickOrder[j];
    const k = E.back(prog(t, appear, appear + 0.16));
    const cols = WALLS[w].cols;
    const along = (w === 0 || w === 2) ? Wd - P : Dd - P;
    const bw = along / cols, bh = Hh / ROWS;
    const a = -along / 2 + (c + 0.5) * bw;
    const yy = 0.11 + (r + 0.5) * bh + (1 - k) * 0.35;
    if (w === 0) pos.set(a, yy, Dd / 2 - P / 2);
    else if (w === 2) pos.set(a, yy, -(Dd / 2 - P / 2));
    else if (w === 1) pos.set(Wd / 2 - P / 2, yy, a);
    else pos.set(-(Wd / 2 - P / 2), yy, a);
    const s = Math.max(0.001, prog(t, appear, appear + 0.08));
    if (w === 0 || w === 2) scl.set(bw * 0.95 * s, bh * 0.92 * s, WALL_T * s); else scl.set(WALL_T * s, bh * 0.92 * s, bw * 0.95 * s);
    m4.compose(pos, q, scl);
    bricks.setMatrixAt(n++, m4);
  }
  bricks.count = n;
  bricks.instanceMatrix.needsUpdate = true;
  // cardboard
  card.visible = t >= 5.2 && t < 8.6;
  if (card.visible) {
    const drop = E.bounce(prog(t, 5.2, 5.5));
    const sag = kf(t, [[6.35, 0], [7.12, 0.14, E.io], [7.38, 0.6, E.in]]);
    const fly = E.in(prog(t, 8.05, 8.55));
    card.position.set(fly * 3.5, 0.11 + 0.5 + 0.03 + (1 - drop) * 2.5 + fly * 2.2, 0);
    card.rotation.z = -fly * 2.5;
    card.scale.setScalar(1 - fly * 0.7);
    cardHalves[0].rotation.z = sag; cardHalves[1].rotation.z = -sag;
    const wet = prog(t, 6.1, 7.1);
    cardMat.color.setRGB(1 - wet * 0.35, 1 - wet * 0.38, 1 - wet * 0.4);
  }
  // roof
  roof.visible = t >= 8.6;
  if (roof.visible) {
    const rw = roofW(t), rd = roofD(t), rise = roofRise(rw);
    const drop = E.bounce(prog(t, 8.6, 9.0));
    roof.position.set(0, 0.11 + Hh + (1 - drop) * 2.8, 0);
    const half = rw / 2, len = Math.hypot(half, rise), ang = Math.atan2(rise, half);
    slabs[0].scale.set(len + 0.06, 1, rd); slabs[0].position.set(-half / 2, rise / 2 + 0.04, 0); slabs[0].rotation.z = ang;
    slabs[1].scale.set(len + 0.06, 1, rd); slabs[1].position.set(half / 2, rise / 2 + 0.04, 0); slabs[1].rotation.z = -ang;
    const gw = Math.min(rw - 0.25, Wd), gh = rise * gw / rw;
    gables[0].scale.set(gw, gh, 1); gables[0].position.set(0, 0, Math.min(rd / 2 - 0.2, Dd / 2 - 0.1) - 0.08);
    gables[1].scale.set(gw, gh, 1); gables[1].position.set(0, 0, -Math.min(rd / 2 - 0.2, Dd / 2 - 0.1));
    ridge.scale.set(1, rd + 0.06, 1); ridge.position.set(0, rise + 0.1, 0);
  }
  // door
  const doorW = (Wd - P) / 3 - 0.04, doorH = Hh * 5 / 6 - 0.03;
  const dd = E.bounce(prog(t, 21.05, 21.4));
  doorHinge.visible = t >= 21.05;
  doorHinge.position.set(-doorW / 2, 0.11 + (1 - dd) * 3, Dd / 2 - P / 2 + 0.07);
  doorHinge.rotation.y = kf(t, [[25.4, 0], [25.8, -1.75, E.out], [28.0, -1.75], [28.3, 0, E.in]]);
  doorPanel.scale.set(doorW, doorH, 1); doorPanel.position.set(doorW / 2, doorH / 2, 0);
  knob.position.set(doorW * 0.82, doorH * 0.47, 0.07);
  const lit = E.out(prog(t, 28.45, 28.75));
  doorLamp.visible = t >= 21.05;
  doorLamp.position.set(0, 0.11 + Hh * 5 / 6 + 0.18, Dd / 2 - P / 2 + 0.16);
  doorLamp.material.emissiveIntensity = lit * 2.2;
  // windows
  const winT = [21.35, 21.75];
  windows.forEach((g, i) => {
    const s = E.back(prog(t, winT[i], winT[i] + 0.3));
    g.visible = t >= winT[i];
    g.scale.setScalar(Math.max(0.001, s));
    g.position.set((i ? 1 : -1) * ((Wd - P) / 2 - (Wd - P) / 6 + 0.02), 0.11 + Hh * 0.56, Dd / 2 - P / 2 + WALL_T / 2 + 0.04);
    g.rotation.z = i ? kf(t, [[0, 0.42], [23.0, 0.42], [23.5, 0, E.elastic]]) : 0;
  });
  glassMat.emissiveIntensity = lit * 1.3;
  interiorLight.intensity = lit * 3; interiorLight.position.set(0, 1.4, 0);
  // puddle
  const pr = kf(t, [[17.9, 0], [19.8, 0.95, E.out], [20.9, 0.95], [21.4, 0, E.in]]);
  puddle.visible = pr > 0.01;
  puddle.scale.set(pr * 1.2, 1, pr * 0.9); puddle.position.set(0.2, 0.17, 0.0);
  return { Wd, Dd, Hh };
}

function updateRain(t, hs) {
  const amt = rainAmount(t);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), pos = new THREE.Vector3(), s1 = new THREE.Vector3(1, 1, 1), s0 = new THREE.Vector3(0, 0, 0);
  q.setFromEuler(new THREE.Euler(0, 0, 0.12));
  const rw = roofW(t), rd = roofD(t), rise = roofRise(rw);
  const cardOk = t >= 5.5 && t < 7.15;
  for (let i = 0; i < RAIN_N; i++) {
    const hx = hash(i), hz = hash(i + 1000), hy = hash(i + 2000), hv = hash(i + 3000);
    const x = -6 + hx * 12, z = -4.5 + hz * 12;
    const span = 10, sp = 9 + hv * 3;
    const y = span - ((t * sp + hy * span) % span) - 0.2;
    let visible = hv < amt;
    if (visible && cardOk && Math.abs(x) < 0.82 && Math.abs(z) < 0.67 && y < 0.7) visible = false;
    if (visible && t >= 9.0 && Math.abs(x) < rw / 2 && Math.abs(z) < rd / 2 && y < 0.11 + hs.Hh + rise * (1 - Math.abs(x) / (rw / 2)) + 0.15) visible = false;
    if (y < 0.1) visible = false;
    pos.set(x - (y * 0.12), y, z);
    m4.compose(pos, q, visible ? s1 : s0);
    rain.setMatrixAt(i, m4);
  }
  rain.instanceMatrix.needsUpdate = true;
  rain.visible = amt > 0.001;
  // wind flakes (scene 1)
  const fa = 1 - prog(t, 3.8, 4.6);
  flakes.visible = fa > 0.01;
  flakes.material.opacity = 0.85 * fa;
  for (let i = 0; i < FLAKE_N; i++) {
    const sp = 1.8 + hash(i + 50) * 1.5;
    const x = -6 + ((t * sp + hash(i + 70) * 9) % 9);
    const y = 0.3 + hash(i + 90) * 3.2 + Math.sin(t * 2 + i) * 0.15;
    const z = 0.2 + hash(i + 110) * 3.6;
    m4.makeTranslation(x - 2, y, z);
    flakes.setMatrixAt(i, m4);
  }
  flakes.instanceMatrix.needsUpdate = true;
  // atmosphere
  const cold = 1 - prog(t, 3.5, 5.0);
  const sky = SKY_CLEAR.clone().lerp(SKY_COLD, cold * 0.8).lerp(SKY_RAIN, amt * 0.85);
  scene.background.copy(sky); scene.fog.color.copy(sky);
  sun.intensity = 2.3 - amt * 1.1;
  hemi.intensity = 1.55 - amt * 0.35;
  ground.material.color.setHex(0xCFD3D6).multiplyScalar(1 - amt * 0.12);
}

function updateFx(t) {
  const head = new THREE.Vector3();
  ch.head.getWorldPosition(head);
  head.y += 1.25;
  const showPop = (m, a, b, up = 0) => {
    if (!m) return;
    m.visible = t >= a && t < b;
    const s = E.back(prog(t, a, a + 0.25)) * (1 - E.in(prog(t, b - 0.15, b)));
    m.scale.setScalar(Math.max(0.001, s));
    m.position.copy(head).add(new THREE.Vector3(0.3, up + Math.sin(t * 6) * 0.04, 0));
    m.quaternion.copy(camera.quaternion);
    m.rotateZ(Math.sin(t * 8) * 0.12);
  };
  showPop(bang, 2.45, 3.85, -0.3);
  showPop(quest, 14.7, 15.95);
  const on = (t >= 12.65 && t < 13.4) || (t >= 13.68 && t < 14.4);
  stars.forEach((s, i) => {
    s.visible = on;
    const a = t * 7 + i * (Math.PI * 2 / 3);
    s.position.set(head.x + Math.cos(a) * 0.42, head.y - 0.75 + Math.sin(a * 2) * 0.03, head.z + Math.sin(a) * 0.42);
    s.rotation.set(0, t * 4, t * 3);
  });
}

const CAM = [
  [0.0, [-3.0, 1.6, 5.9], [-3.1, 1.2, 1.9]],
  [2.4, [-1.15, 1.65, 5.5], [-1.1, 1.25, 1.9]],
  [3.7, [-1.1, 1.9, 5.0], [-1.1, 1.6, 1.9]],
  [4.5, [-0.45, 2.5, 6.9], [-0.45, 0.85, 0.5]],
  [7.9, [-0.4, 2.4, 6.5], [-0.45, 0.8, 0.5]],
  [8.6, [0.1, 2.6, 6.9], [-0.3, 0.9, 0.3]],
  [11.9, [0.2, 2.5, 6.6], [-0.3, 0.9, 0.3]],
  [12.45, [3.1, 2.0, 4.6], [0.15, 0.95, 0.8]],
  [15.9, [3.3, 2.0, 4.8], [0.15, 0.95, 0.8]],
  [16.6, [3.0, 3.6, 7.4], [0.2, 1.2, 0.1]],
  [17.7, [2.6, 6.0, 7.8], [0.6, 1.3, 0.3]],
  [19.9, [2.4, 6.2, 7.4], [0.6, 1.2, 0.3]],
  [20.7, [1.2, 2.5, 8.6], [0.35, 1.45, 0.4]],
  [24.5, [0.8, 2.4, 7.9], [0.1, 1.45, 0.4]],
  [30.0, [0.0, 3.0, 12.0], [0.0, 1.55, 0.0]],
];
function updateCamera(t) {
  const keysP = CAM.map(([tt, p]) => [tt, p, E.io]);
  const keysT = CAM.map(([tt, , g]) => [tt, g, E.io]);
  camera.position.set(...kf(t, keysP));
  camera.lookAt(new THREE.Vector3(...kf(t, keysT)));
  camera.updateMatrixWorld();
}

function renderAt(t) {
  const hs = updateHouse(t);
  updateChar(t);
  updateCamera(t);
  updateRain(t, hs);
  updateFx(t);
  renderer.render(scene, camera);
}
window.renderAt = (t, q = 0.92) => { renderAt(t); return renderer.domElement.toDataURL('image/jpeg', q); };
window.ready = loadFont().then(() => { renderAt(0); return true; });
