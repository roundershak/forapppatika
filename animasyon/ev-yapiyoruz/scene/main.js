// "Sıfırdan Ev Yapıyoruz" v2 — crisp low-poly scene, self-assembling house.
// window.renderAt(t) draws the frame at time t (seconds) and returns a JPEG data URL.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';

const params = new URLSearchParams(location.search);
const VW = +(params.get('w') || 1080), VH = +(params.get('h') || 1920);

// ---------- math ----------
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const lerp = (a, b, p) => a + (b - a) * p;
const prog = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
const E = {
  lin: x => x,
  io: x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  out: x => 1 - Math.pow(1 - x, 3),
  in: x => x * x * x,
  back: x => { const c1 = 1.7, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
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
function kf(t, keys) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, v0] = keys[i], [t1, v1, e] = keys[i + 1];
    if (t <= t1) return lerpV(v0, v1, (e || E.io)((t - t0) / (t1 - t0)));
  }
  return keys[keys.length - 1][1];
}
function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const hash = i => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const V3 = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------- renderer ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(VW, VH);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.02;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, VW / VH, 0.1, 160);

// sky dome
const SKY = { top: new THREE.Color(0x4F9BDB), hor: new THREE.Color(0xCFE7F5), rainTop: new THREE.Color(0x7D8C9C), rainHor: new THREE.Color(0xB3BEC8), coldTop: new THREE.Color(0x7FA6C9), coldHor: new THREE.Color(0xDCE7EF) };
const skyMat = new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false,
  uniforms: { top: { value: SKY.top.clone() }, hor: { value: SKY.hor.clone() } },
  vertexShader: 'varying vec3 vp; void main(){ vp = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
  fragmentShader: 'uniform vec3 top; uniform vec3 hor; varying vec3 vp; void main(){ float h = clamp(vp.y*1.6, 0.0, 1.0); gl_FragColor = vec4(mix(hor, top, pow(h,0.8)), 1.0); }',
});
const sky = new THREE.Mesh(new THREE.SphereGeometry(120, 32, 16), skyMat);
scene.add(sky);
scene.fog = new THREE.Fog(SKY.hor.clone(), 28, 80);

const hemi = new THREE.HemisphereLight(0xffffff, 0x8FA36A, 1.35);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xFFF1DC, 2.6);
sun.position.set(7, 12, 9);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -10, right: 10, top: 10, bottom: -10, near: 1, far: 45 });
sun.shadow.bias = -0.0003;
sun.shadow.normalBias = 0.02;
sun.shadow.radius = 2;
scene.add(sun);

// ---------- materials ----------
const M = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.82, metalness: 0, ...o });
const MF = (color, o = {}) => M(color, { flatShading: true, ...o });
const BX = (w, h, d, r = 0.012) => (r > 0 ? new RoundedBoxGeometry(w, h, d, 1, r) : new THREE.BoxGeometry(w, h, d));
const UNIT = new THREE.BoxGeometry(1, 1, 1);
function mesh(geo, mat, parent, shadow = true) {
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = shadow; m.receiveShadow = true;
  (parent || scene).add(m);
  return m;
}
function canvasTex(size, draw, repeat = [1, 1]) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  draw(c.getContext('2d'), size);
  const tx = new THREE.CanvasTexture(c);
  tx.colorSpace = THREE.SRGBColorSpace; tx.wrapS = tx.wrapT = THREE.RepeatWrapping; tx.repeat.set(...repeat); tx.anisotropy = 8;
  return tx;
}
const rnd = mulberry32(5);
const speckle = (base, cols, n, sz) => (g, s) => { g.fillStyle = base; g.fillRect(0, 0, s, s); for (let i = 0; i < n; i++) { g.fillStyle = cols[i % cols.length]; const r = sz * (0.5 + rnd()); g.fillRect(rnd() * s, rnd() * s, r, r); } };
const grassTex = canvasTex(512, speckle('#79B04A', ['#6FA542', '#86BC55', '#72A946', '#8DC25B'], 2600, 5), [26, 26]);
const soilTex = canvasTex(512, speckle('#8A6440', ['#7A5636', '#987150', '#6E4D30', '#A07A55'], 2200, 5), [3, 3]);
const woodTex = canvasTex(256, (g, s) => {
  g.fillStyle = '#fff'; g.fillRect(0, 0, s, s);
  for (let y = 0; y < s; y += 4) { g.fillStyle = `rgba(90,55,25,${0.04 + rnd() * 0.08})`; g.fillRect(0, y, s, 2); }
  for (let y = 0; y < s; y += 64) { g.fillStyle = 'rgba(70,40,15,0.35)'; g.fillRect(0, y, s, 3); }
});
const cardboardTex = canvasTex(256, (g, s) => {
  g.fillStyle = '#C69A62'; g.fillRect(0, 0, s, s);
  for (let x = 0; x < s; x += 9) { g.fillStyle = 'rgba(110,70,30,0.2)'; g.fillRect(x, 0, 3, s); }
  g.fillStyle = '#E3CB97'; g.fillRect(0, s * 0.45, s, s * 0.1);
});
const foamTex = canvasTex(256, (g, s) => {
  g.fillStyle = '#F2C94C'; g.fillRect(0, 0, s, s);
  for (let i = 0; i < 900; i++) { g.fillStyle = rnd() > 0.5 ? 'rgba(255,240,170,0.5)' : 'rgba(200,150,40,0.25)'; g.fillRect(rnd() * s, rnd() * s, 3, 3); }
  g.strokeStyle = 'rgba(160,110,20,0.5)'; g.lineWidth = 4; g.strokeRect(2, 2, s - 4, s - 4);
});
const plasterTex = canvasTex(256, speckle('#F4EEE3', ['#EDE6D9', '#F8F4EC', '#E9E1D2'], 1500, 3));

const COL = {
  concrete: 0xB7B2A8, bricks: [0xB5533A, 0xA84A33, 0xC0623F, 0x9C4430, 0xB95C40], tile: [0xB0412A, 0x9E3823, 0xBF4E31],
  wood: 0xB07A48, woodLight: 0xCFA26A, door: 0x2E7D82, frame: 0xFBFAF6, glass: 0x9ED2EA,
  trunk: 0x6B4A31, leaves: [0x5E9E4A, 0x4C8A3B, 0x74B356, 0x3F7D3A],
  jacket: 0xE6A93A, jacketDark: 0xC88C25, pants: 0x34495E, beanie: 0xC9433A, scarf: 0x2E7D82, skin: 0xEFC3A0, hair: 0x4A3326, shoe: 0x3B2B22, dark: 0x1F1F26,
};

// ---------- world ----------
const ground = mesh(new THREE.PlaneGeometry(200, 200), M(0xffffff, { map: grassTex }), scene, false);
ground.rotation.x = -Math.PI / 2;
const lot = mesh(BX(6.4, 0.06, 5.6, 0.02), M(0xffffff, { map: soilTex }), scene, false);
lot.position.set(0, 0.03, 0.1);
const sidewalk = mesh(BX(80, 0.08, 1.5, 0.02), M(0xD3CCBE), scene, false); sidewalk.position.set(0, 0.04, 3.7);
for (let x = -40; x < 40; x += 1.5) { const j = mesh(new THREE.BoxGeometry(0.03, 0.082, 1.5), M(0xB9B2A4), scene, false); j.position.set(x, 0.041, 3.7); }
const curb = mesh(BX(80, 0.14, 0.22, 0.02), M(0xBDB6A8), scene); curb.position.set(0, 0.07, 4.55);
const road = mesh(new THREE.BoxGeometry(80, 0.02, 7), M(0x5E636B), scene, false); road.position.set(0, 0.01, 8.2);
for (let x = -40; x < 40; x += 3) { const d = mesh(new THREE.BoxGeometry(1.4, 0.025, 0.14), M(0xF2EFE6), scene, false); d.position.set(x, 0.022, 7.9); }
const pathM = mesh(BX(1.1, 0.07, 0.75, 0.02), M(0xD3CCBE), scene, false); pathM.position.set(0, 0.035, 3.05);

const leafMats = COL.leaves.map(c => MF(c));
const trunkMat = MF(COL.trunk);
function tree(x, z, s, kind, seed) {
  const r = mulberry32(seed);
  const g = new THREE.Group(); g.position.set(x, 0, z); g.scale.setScalar(s); g.rotation.y = r() * 6; scene.add(g);
  const tr = mesh(new THREE.CylinderGeometry(0.12, 0.17, 1.4, 6), trunkMat, g); tr.position.y = 0.7;
  if (kind === 'pine') {
    for (let k = 0; k < 3; k++) { const c = mesh(new THREE.ConeGeometry(1.0 - k * 0.25, 1.2, 7), leafMats[3 - (k % 2)], g); c.position.y = 1.5 + k * 0.62; }
  } else {
    const blobs = [[0, 2.0, 0, 0.95], [0.45, 1.75, 0.2, 0.62], [-0.4, 1.8, -0.15, 0.68], [0.05, 2.55, 0.05, 0.6]];
    blobs.forEach(([bx, by, bz, br], i) => { const b = mesh(new THREE.IcosahedronGeometry(br, 0), leafMats[(i + seed) % 3], g); b.position.set(bx, by, bz); b.rotation.set(r() * 3, r() * 3, 0); });
  }
}
[[-4.6, -1.0, 1.15, 'round'], [-6.4, 1.6, 1.0, 'pine'], [4.8, -1.4, 1.2, 'round'], [6.3, 1.5, 0.95, 'pine'], [-4.2, -4.6, 1.3, 'pine'],
 [3.7, -4.9, 1.35, 'round'], [-7.8, -3.2, 1.25, 'round'], [8.0, -3.4, 1.3, 'pine'], [-1.6, -6.4, 1.2, 'round'], [1.9, -7.2, 1.4, 'pine'],
 [-10.5, 0.5, 1.3, 'round'], [10.6, 0.2, 1.2, 'round'], [-12, -6, 1.5, 'pine'], [12.5, -6.5, 1.5, 'round'], [-5.2, 2.4, 0.75, 'round']]
  .forEach(([x, z, s, k], i) => tree(x, z, s, k, i * 13 + 3));
function bush(x, z, s, i) { const b = mesh(new THREE.IcosahedronGeometry(0.42 * s, 0), leafMats[i % 3], scene); b.position.set(x, 0.3 * s, z); b.scale.y = 0.75; b.rotation.y = i; }
[[-3.4, 2.7, 1], [3.4, 2.6, 1.1], [-3.6, -2.6, 0.9], [3.3, -2.9, 1], [-2.9, 3.0, 0.7], [5.5, 3.0, 0.8], [-6.5, 3.1, 0.9]].forEach(([x, z, s], i) => bush(x, z, s, i));
{ // fence behind the lot
  const fm = MF(0xE9DCC4);
  for (let x = -3.2; x <= 3.21; x += 0.8) { const p = mesh(BX(0.1, 0.8, 0.1), fm, scene); p.position.set(x, 0.4, -2.9); }
  for (const y of [0.32, 0.62]) { const r = mesh(BX(6.5, 0.08, 0.05), fm, scene); r.position.set(0, y, -2.9); }
}
{ // flowers & rocks
  const fl = new THREE.InstancedMesh(new THREE.BoxGeometry(0.07, 0.07, 0.07), M(0xffffff), 160);
  const m4 = new THREE.Matrix4(); const cols = [0xFFFFFF, 0xF6D24A, 0xF29BB5, 0xE96B5C];
  let n = 0;
  for (let i = 0; n < 160 && i < 600; i++) {
    const x = (hash(i) - 0.5) * 18, z = -6 + hash(i + 77) * 9.5;
    if (Math.abs(x) < 3.4 && z > -3 && z < 3.1) continue;
    m4.makeTranslation(x, 0.05, z); fl.setMatrixAt(n, m4); fl.setColorAt(n, new THREE.Color(cols[i % 4])); n++;
  }
  fl.count = n; scene.add(fl);
  [[-3.7, 1.2, 0.25], [3.8, 0.4, 0.3], [-2.5, -3.6, 0.2], [4.6, 2.9, 0.18]].forEach(([x, z, s], i) => { const r = mesh(new THREE.DodecahedronGeometry(s, 0), MF(0xA9A59C), scene); r.position.set(x, s * 0.5, z); r.rotation.set(i, i * 2, 0); });
}
{ // distant town + hills
  const r = mulberry32(42), pal = [0xE9DDC9, 0xD8C3A5, 0xC9D6DF, 0xE7CFC0, 0xF0E7DA];
  for (let x = -30; x < 30;) {
    const w = 2 + r() * 2, h = 2.5 + r() * 4.5;
    const b = mesh(BX(w, h, 2.2, 0.03), MF(pal[Math.floor(r() * pal.length)]), scene, false); b.position.set(x + w / 2, h / 2, -15 - r() * 2);
    const rf = mesh(new THREE.ConeGeometry(w * 0.75, 1.1, 4), MF(COL.tile[Math.floor(r() * 3)]), scene, false); rf.position.set(x + w / 2, h + 0.55, b.position.z); rf.rotation.y = Math.PI / 4; rf.scale.z = 0.75;
    x += w + 0.6 + r();
  }
  [[-22, -34, 14], [5, -38, 18], [28, -33, 13]].forEach(([x, z, s]) => { const h = mesh(new THREE.IcosahedronGeometry(s, 1), MF(0x8FB86A), scene, false); h.position.set(x, -s * 0.62, z); });
}
const clouds = [];
for (let i = 0; i < 6; i++) {
  const g = new THREE.Group(); scene.add(g);
  for (let k = 0; k < 4; k++) { const c = mesh(new THREE.IcosahedronGeometry(0.9 + hash(i * 9 + k) * 0.8, 0), MF(0xffffff, { emissive: 0xffffff, emissiveIntensity: 0.25 }), g, false); c.position.set(k * 1.1 - 1.6, hash(i + k) * 0.5, hash(k + i * 3) * 0.6); }
  g.userData = { x: -26 + i * 10 + hash(i) * 4, y: 11 + hash(i + 4) * 4, z: -22 - hash(i + 8) * 8 };
  clouds.push(g);
}
function lamp(x, z) {
  const p = mesh(new THREE.CylinderGeometry(0.06, 0.08, 3.4, 8), M(0x50565E), scene); p.position.set(x, 1.7, z);
  const hd = mesh(BX(0.32, 0.36, 0.32, 0.02), M(0xFFF3D6, { emissive: 0xFFD27A, emissiveIntensity: 0.2 }), scene); hd.position.set(x, 3.55, z);
  const cap = mesh(new THREE.ConeGeometry(0.3, 0.2, 4), M(0x50565E), scene); cap.position.set(x, 3.83, z); cap.rotation.y = Math.PI / 4;
}
lamp(-5.0, 4.25); lamp(5.2, 4.25);

// ---------- character ----------
function makeChar() {
  const root = new THREE.Group(); scene.add(root); root.scale.setScalar(0.92);
  const body = new THREE.Group(); root.add(body);
  const jacket = M(COL.jacket), jd = M(COL.jacketDark), pants = M(COL.pants), skin = M(COL.skin), dark = M(COL.dark, { roughness: 0.35 });
  const legs = [];
  for (const s of [-1, 1]) {
    const hip = new THREE.Group(); hip.position.set(0.12 * s, 0.88, 0); body.add(hip);
    mesh(BX(0.18, 0.8, 0.2, 0.02), pants, hip).position.y = -0.4;
    mesh(BX(0.21, 0.13, 0.32, 0.03), M(COL.shoe), hip).position.set(0, -0.8, 0.05);
    legs.push(hip);
  }
  mesh(BX(0.56, 0.68, 0.33, 0.03), jacket, body).position.y = 1.22;
  mesh(BX(0.58, 0.1, 0.35, 0.02), jd, body).position.y = 0.92;
  mesh(BX(0.025, 0.6, 0.01, 0), M(0x7A5A1E), body).position.set(0, 1.2, 0.168);
  for (const s of [-1, 1]) mesh(BX(0.13, 0.11, 0.02, 0.01), jd, body).position.set(0.15 * s, 1.03, 0.17);
  mesh(BX(0.62, 0.13, 0.38, 0.03), M(COL.scarf), body).position.y = 1.56;
  const tail = mesh(BX(0.12, 0.34, 0.05, 0.015), M(COL.scarf), body); tail.position.set(0.14, 1.38, 0.19);
  const arms = [];
  for (const s of [-1, 1]) {
    const sh = new THREE.Group(); sh.position.set(0.355 * s, 1.48, 0); body.add(sh);
    mesh(BX(0.15, 0.6, 0.17, 0.025), jacket, sh).position.y = -0.3;
    mesh(BX(0.16, 0.06, 0.18, 0.015), jd, sh).position.y = -0.6;
    mesh(BX(0.12, 0.14, 0.13, 0.03), skin, sh).position.y = -0.7;
    arms.push(sh);
  }
  const head = new THREE.Group(); head.position.y = 1.62; body.add(head);
  const skull = mesh(BX(0.44, 0.47, 0.41, 0.05), skin, head); skull.position.y = 0.25;
  for (const s of [-1, 1]) mesh(BX(0.05, 0.1, 0.08, 0.015), skin, head).position.set(0.235 * s, 0.24, 0);
  for (const s of [-1, 1]) mesh(BX(0.05, 0.12, 0.34, 0.01), M(COL.hair), head).position.set(0.215 * s, 0.38, -0.02);
  mesh(BX(0.46, 0.14, 0.12, 0.01), M(COL.hair), head).position.set(0, 0.38, -0.16);
  mesh(BX(0.48, 0.17, 0.45, 0.04), M(COL.beanie), head).position.y = 0.52;
  mesh(BX(0.5, 0.08, 0.47, 0.02), M(0xA8352E), head).position.y = 0.44;
  mesh(new THREE.IcosahedronGeometry(0.07, 0), MF(0xF4EEE3), head).position.y = 0.65;
  const frost = new THREE.Group(); head.add(frost);
  mesh(BX(0.5, 0.07, 0.47, 0.03), M(0xF7FBFF, { emissive: 0xE8F2FF, emissiveIntensity: 0.3 }), frost).position.y = 0.62;
  const frostSh = new THREE.Group(); body.add(frostSh);
  for (const s of [-1, 1]) mesh(BX(0.2, 0.05, 0.36, 0.02), M(0xF7FBFF), frostSh).position.set(0.2 * s, 1.64, 0);
  const face = new THREE.Group(); face.position.set(0, 0.24, 0.207); head.add(face);
  const eyes = [], arcs = [], brows = [];
  for (const s of [-1, 1]) {
    const e = mesh(BX(0.055, 0.075, 0.02, 0.008), dark, face, false); e.position.set(0.095 * s, 0.035, 0);
    const hl = mesh(new THREE.BoxGeometry(0.016, 0.016, 0.01), M(0xffffff, { emissive: 0xffffff }), e, false); hl.position.set(0.012, 0.018, 0.012);
    eyes.push(e);
    const a = mesh(new THREE.TorusGeometry(0.033, 0.011, 4, 10, Math.PI), dark, face, false); a.position.set(0.095 * s, 0.025, 0.005); a.visible = false; arcs.push(a);
    const b = mesh(BX(0.085, 0.022, 0.02, 0.005), M(COL.hair), face, false); b.position.set(0.095 * s, 0.11, 0.003); brows.push(b);
  }
  mesh(BX(0.06, 0.075, 0.05, 0.012), M(0xE5AE88), face, false).position.set(0, -0.02, 0.02);
  for (const s of [-1, 1]) { const c = mesh(new THREE.CircleGeometry(0.035, 12), M(0xEE9C8E, { transparent: true, opacity: 0.75 }), face, false); c.position.set(0.15 * s, -0.04, 0.004); }
  const mouth = new THREE.Group(); mouth.position.set(0, -0.105, 0.006); face.add(mouth);
  const m = {
    smile: mesh(new THREE.TorusGeometry(0.05, 0.012, 4, 14, Math.PI), dark, mouth, false),
    grin: mesh(new THREE.CircleGeometry(0.065, 16, Math.PI, Math.PI), M(0x7A2E2E), mouth, false),
    o: mesh(new THREE.TorusGeometry(0.03, 0.013, 6, 14), dark, mouth, false),
    flat: mesh(BX(0.09, 0.02, 0.015, 0.005), dark, mouth, false),
    frown: mesh(new THREE.TorusGeometry(0.045, 0.012, 4, 14, Math.PI), dark, mouth, false),
  };
  m.smile.rotation.z = Math.PI; m.grin.position.y = 0.02; m.o.scale.y = 1.3; m.frown.position.y = -0.035;
  return { root, body, legs, arms, head, eyes, arcs, brows, mouth, m, frost, frostSh, skin };
}
const ch = makeChar();

// ---------- house ----------
const W = 3.4, D = 2.8, H = 2.8, P = 0.4, T = 0.22, ROWS = 12, BASE = 0.28;
const RW = W + 0.7, RD = D + 0.7, RISE = 1.4;
const ROOF_Y = BASE + H;
const zF = D / 2 - P / 2, xR = W / 2 - P / 2;
const OPEN = [[-0.41, 0.41, 0, 2.33], [0.682, 1.227, 1.165, 2.1], [-1.227, -0.682, 1.165, 2.1]];
const WALLS = [
  { c: V3(0, 0, zF), a: V3(1, 0, 0), n: V3(0, 0, 1), L: W - P, cols: 11, front: true },
  { c: V3(xR, 0, 0), a: V3(0, 0, -1), n: V3(1, 0, 0), L: D - P, cols: 9 },
  { c: V3(0, 0, -zF), a: V3(-1, 0, 0), n: V3(0, 0, -1), L: W - P, cols: 11 },
  { c: V3(-xR, 0, 0), a: V3(0, 0, 1), n: V3(-1, 0, 0), L: D - P, cols: 9 },
];
const inOpen = (u, v) => OPEN.some(([u0, u1, v0, v1]) => u > u0 && u < u1 && v > v0 && v < v1);

// generic flying part: appears exploded, hovers, then snaps into place
const parts = [];
function part(obj, t0, dur, off, rot = [0, 0, 0], hover = 0.35, ease = E.out) {
  const p = { obj, t0, dur, off, rot: new THREE.Euler(...rot), hover, ease, pos: obj.position.clone(), q: obj.quaternion.clone(), s: obj.scale.clone() };
  parts.push(p); return p;
}
const _q = new THREE.Quaternion();
function updatePart(p, t) {
  const o = p.obj;
  o.visible = t >= p.t0 - p.hover;
  if (!o.visible) return;
  const k = p.ease(prog(t, p.t0, p.t0 + p.dur));
  const a = E.back(prog(t, p.t0 - p.hover, p.t0 - p.hover + 0.2));
  o.position.copy(p.pos).addScaledVector(p.off, 1 - k);
  o.position.y += (1 - k) * Math.sin(t * 3 + p.pos.x * 2) * 0.05;
  _q.setFromEuler(new THREE.Euler(p.rot.x * (1 - k), p.rot.y * (1 - k), p.rot.z * (1 - k)));
  o.quaternion.copy(p.q).premultiply(_q);
  o.scale.copy(p.s).multiplyScalar(Math.max(0.001, a));
}
const R3 = (i, amp) => [(hash(i) - 0.5) * amp, (hash(i + 5) - 0.5) * amp, (hash(i + 9) - 0.5) * amp];

// foundation (4 slabs)
const concreteM = M(COL.concrete);
[[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sz], i) => {
  const s = mesh(BX((W + 0.4) / 2 - 0.01, 0.22, (D + 0.4) / 2 - 0.01, 0.015), concreteM);
  s.position.set(sx * (W + 0.4) / 4, BASE - 0.11, sz * (D + 0.4) / 4);
  part(s, 4.3 + i * 0.12, 0.4, V3(sx * 2.4, 0.8, sz * 2.0), R3(i, 1.2), 0.3);
});
// floor (wood) appears with walls
const floor = mesh(BX(W - 0.3, 0.03, D - 0.3, 0.01), M(COL.woodLight, { map: woodTex }), scene, false);
floor.position.set(0, BASE + 0.015, 0);
part(floor, 8.2, 0.35, V3(0, 1.5, 0), [0, 0, 0], 0.2);
// corner posts
const posts = [[-1, 1], [1, 1], [1, -1], [-1, -1]].map(([sx, sz]) => {
  const p = mesh(BX(P, 1, P, 0.015), M(COL.concrete)); p.position.set(sx * xR, 0, sz * zF); return p;
});
// bricks (instanced)
const brickList = [];
for (let r = 0; r < ROWS; r++) WALLS.forEach((w, wi) => {
  for (let c = 0; c < w.cols; c++) {
    const u = -w.L / 2 + (c + 0.5) * w.L / w.cols, v = (r + 0.5) * H / ROWS;
    if (w.front && inOpen(u, v)) continue;
    brickList.push({ wi, u, v, bw: w.L / w.cols, i: brickList.length });
  }
});
const bricks = new THREE.InstancedMesh(new RoundedBoxGeometry(1, 1, 1, 1, 0.03), M(0xffffff, { roughness: 0.9 }), brickList.length);
bricks.castShadow = bricks.receiveShadow = true; scene.add(bricks);
brickList.forEach((b, i) => bricks.setColorAt(i, new THREE.Color(COL.bricks[Math.floor(hash(i + 31) * COL.bricks.length)])));
// cardboard
const cardMat = M(0xffffff, { map: cardboardTex });
const card = new THREE.Group(); scene.add(card);
const cardHalves = [-1, 1].map(s => { const pv = new THREE.Group(); pv.position.x = 1.72 * s; card.add(pv); mesh(new THREE.BoxGeometry(1.74, 0.04, 3.0), cardMat, pv).position.x = -0.87 * s; return pv; });
// roof frame: wall plates, ridge, rafters
const woodM = M(COL.wood, { map: woodTex });
const SL = Math.hypot(RW / 2, RISE), ANG = Math.atan2(RISE, RW / 2);
{
  let k = 0;
  for (const sz of [-1, 1]) { const b = mesh(BX(W, 0.14, 0.18, 0.01), woodM); b.position.set(0, ROOF_Y + 0.07, sz * zF); part(b, 10.25 + k * 0.05, 0.35, V3(0, 2.5, sz * 1.5), R3(k + 40, 0.8), 0.3); k++; }
  const ridge = mesh(BX(0.16, 0.18, RD, 0.01), woodM); ridge.position.set(0, ROOF_Y + RISE, 0); part(ridge, 10.4, 0.35, V3(0, 3, 0), [0, 0, 0.6], 0.3);
  for (let i = 0; i < 6; i++) for (const sx of [-1, 1]) {
    const z = -RD / 2 + 0.12 + i * (RD - 0.24) / 5;
    const r = mesh(BX(SL, 0.14, 0.1, 0.01), woodM);
    r.position.set(sx * RW / 4, ROOF_Y + RISE / 2, z); r.rotation.z = -sx * ANG;
    part(r, 10.45 + i * 0.06 + (sx > 0 ? 0.03 : 0), 0.35, V3(sx * 2.2, 2.4, 0), R3(i * 2 + sx + 50, 1.4), 0.3);
  }
}
// roof deck boards (with gaps -> leaks)
for (const sx of [-1, 1]) for (let j = 0; j < 4; j++) {
  const w = SL / 4 - 0.06, d0 = -SL / 2 + (j + 0.5) * SL / 4;
  const b = mesh(BX(w, 0.05, RD, 0.008), M(COL.woodLight, { map: woodTex }));
  const cx = sx * RW / 4 + Math.cos(ANG) * d0 * sx, cy = ROOF_Y + RISE / 2 - Math.sin(ANG) * d0 + 0.1;
  b.position.set(cx, cy, 0); b.rotation.z = -sx * ANG;
  part(b, 10.85 + j * 0.07 + (sx > 0 ? 0.035 : 0), 0.3, V3(sx * 1.2, 2.2, 0), R3(j * 3 + sx + 70, 0.9), 0.25);
}
// gables (wood boards)
const tri = new THREE.Shape(); tri.moveTo(-0.5, 0); tri.lineTo(0.5, 0); tri.lineTo(0, 1); tri.closePath();
const triGeo = new THREE.ExtrudeGeometry(tri, { depth: 0.08, bevelEnabled: false });
for (const sz of [-1, 1]) {
  const g = mesh(triGeo, M(COL.woodLight, { map: woodTex }));
  g.scale.set(W, RISE * W / RW, 1); g.position.set(0, ROOF_Y, sz * zF - 0.04);
  part(g, 11.0 + (sz > 0 ? 0.1 : 0), 0.35, V3(0, 0.5, sz * 2.4), [sz * 0.8, 0, 0], 0.25);
}
// insulation + plaster panels
function wallRects(w) {
  if (w.front) return [[-1.5, -1.227, 0, H], [-1.227, -0.682, 0, 1.165], [-1.227, -0.682, 2.1, H], [-0.682, -0.41, 0, H], [-0.41, 0.41, 2.33, H],
    [0.41, 0.682, 0, H], [0.682, 1.227, 0, 1.165], [0.682, 1.227, 2.1, H], [1.227, 1.5, 0, H]];
  const h = w.L / 2; return [[-h, 0, 0, H / 2], [0, h, 0, H / 2], [-h, 0, H / 2, H], [0, h, H / 2, H]];
}
const foamM = M(0xffffff, { map: foamTex, roughness: 0.95 }), plasterM = M(0xffffff, { map: plasterTex });
const plasterParts = [];
{
  let k = 0;
  WALLS.forEach(w => wallRects(w).forEach(([u0, u1, v0, v1]) => {
    for (const [mat, th, offs, t0, layer] of [[foamM, 0.07, 0, 16.15, 0], [plasterM, 0.03, 0.07, 16.95, 1]]) {
      const pm = mesh(UNIT, mat);
      const along = u1 - u0, hh = v1 - v0, um = (u0 + u1) / 2, vm = (v0 + v1) / 2;
      const pos = w.c.clone().addScaledVector(w.a, um).addScaledVector(w.n, T / 2 + offs + th / 2); pos.y = BASE + vm;
      pm.position.copy(pos);
      pm.scale.set(Math.abs(w.a.x) > 0.5 ? along : th, hh, Math.abs(w.a.x) > 0.5 ? th : along);
      if (layer === 0) part(pm, t0 + k * 0.035, 0.35, w.n.clone().multiplyScalar(2.2).add(V3(0, 0.6, 0)), R3(k + 90, 1.2), 0.3);
      else plasterParts.push({ m: pm, t0: t0 + k * 0.03, s: pm.scale.clone(), p: pm.position.clone(), hh });
    }
    k++;
  }));
}
// roof tiles
const tileMats = COL.tile.map(c => M(c, { roughness: 0.7 }));
{
  const rows = 7, segs = 5;
  for (const sx of [-1, 1]) for (let r = 0; r < rows; r++) for (let s = 0; s < segs; s++) {
    const w = SL / rows * 1.12, d0 = -SL / 2 + (r + 0.5) * SL / rows;
    const segD = (RD + 0.1) / segs;
    const tl = mesh(BX(w, 0.07, segD - 0.015, 0.015), tileMats[(r + s) % 3]);
    tl.position.set(sx * RW / 4 + Math.cos(ANG) * d0 * sx, ROOF_Y + RISE / 2 - Math.sin(ANG) * d0 + 0.17 + r * 0.004, -RD / 2 - 0.05 + (s + 0.5) * segD);
    tl.rotation.z = -sx * (ANG + 0.05);
    const order = (rows - 1 - r) * segs + s;
    part(tl, 20.1 + order * 0.028 + (sx > 0 ? 0.014 : 0), 0.3, V3(sx * 0.8, 2.6, 0), R3(order + sx * 100, 2.0), 0.3);
  }
  const cap = mesh(BX(0.32, 0.14, RD + 0.15, 0.03), tileMats[1]); cap.position.set(0, ROOF_Y + RISE + 0.2, 0);
  part(cap, 21.15, 0.3, V3(0, 2.5, 0), [0, 0.5, 0], 0.25);
  const chim = mesh(BX(0.45, 1.0, 0.45, 0.015), M(COL.bricks[0])); chim.position.set(1.05, ROOF_Y + RISE * 0.72 + 0.35, -0.6);
  part(chim, 21.2, 0.35, V3(1.5, 3, 0), [0, 0.8, 0.4], 0.25);
  const ccap = mesh(BX(0.56, 0.08, 0.56, 0.015), M(COL.concrete)); ccap.position.set(1.05, ROOF_Y + RISE * 0.72 + 0.89, -0.6);
  part(ccap, 21.3, 0.3, V3(0, 2, 0), [0, 0, 0], 0.2);
}
// door
const doorHinge = new THREE.Group(); doorHinge.position.set(-0.4, BASE, zF); scene.add(doorHinge);
const doorM = M(COL.door, { map: woodTex });
for (let i = 0; i < 3; i++) {
  const pl = mesh(BX(0.262, 2.3, 0.07, 0.01), doorM, doorHinge); pl.position.set(0.135 + i * 0.265, 1.15, 0);
  part(pl, 21.25 + i * 0.06, 0.3, V3((i - 1) * 0.9, 0.6, 1.4), R3(i + 140, 1.0), 0.3);
}
const knob = mesh(new THREE.SphereGeometry(0.045, 10, 8), M(0xE0B04A, { metalness: 0.5, roughness: 0.3 }), doorHinge); knob.position.set(0.68, 1.12, 0.06);
part(knob, 21.5, 0.2, V3(0.4, 0.3, 1.0), [0, 0, 0], 0.2);
const frameM = M(COL.frame);
for (const [w, h, x, y] of [[0.1, 2.38, -0.46, 1.19], [0.1, 2.38, 0.46, 1.19], [1.02, 0.1, 0, 2.38]]) {
  const f = mesh(BX(w, h, 0.08, 0.01), frameM); f.position.set(x, BASE + y, zF + T / 2 + 0.12);
  part(f, 21.3, 0.3, V3(x * 2, 0.5, 1.2), [0, 0, x], 0.25);
}
const doorLamp = mesh(BX(0.16, 0.2, 0.12, 0.02), M(0xFFF1CF, { emissive: 0xFFC766, emissiveIntensity: 0 }));
doorLamp.position.set(0, BASE + 2.62, zF + T / 2 + 0.16);
part(doorLamp, 21.55, 0.25, V3(0, 1, 1), [0, 0, 0], 0.2);
// windows
const glassMat = M(COL.glass, { roughness: 0.12, metalness: 0.1, emissive: 0xFFC766, emissiveIntensity: 0 });
const windows = [-1, 1].map((s, wi) => {
  const g = new THREE.Group(); g.position.set(s * 0.955, BASE + 1.633, zF + T / 2 + 0.13); scene.add(g);
  const t0 = 21.5 + wi * 0.3;
  const pieces = [
    [BX(0.66, 0.08, 0.08), 0, 0.51], [BX(0.66, 0.08, 0.08), 0, -0.51], [BX(0.08, 1.1, 0.08), -0.29, 0], [BX(0.08, 1.1, 0.08), 0.29, 0],
    [BX(0.05, 0.98, 0.06), 0, 0], [BX(0.52, 0.05, 0.06), 0, 0.05],
  ];
  pieces.forEach(([geo, x, y], i) => { const m = mesh(geo, frameM, g); m.position.set(x, y, 0.01); part(m, t0 + i * 0.03, 0.3, V3(x * 3 + (hash(i) - 0.5), y * 2 + 0.5, 1.2), R3(i + wi * 10 + 160, 1.5), 0.25); });
  const gl = mesh(BX(0.52, 0.96, 0.03, 0.005), glassMat, g); gl.position.z = -0.01;
  part(gl, t0 + 0.1, 0.3, V3(0, 0.4, 1.6), [0.6, 0, 0], 0.25);
  const sill = mesh(BX(0.8, 0.07, 0.2, 0.015), M(COL.concrete), g); sill.position.set(0, -0.58, 0.05);
  part(sill, t0 + 0.2, 0.25, V3(0, -0.6, 1.0), [0, 0, 0.4], 0.2);
  return g;
});
const puddle = mesh(new THREE.CylinderGeometry(1, 1, 0.015, 24), M(0x7FB6DC, { roughness: 0.05, transparent: true, opacity: 0.85 }), scene, false);
const smoke = [0, 1, 2, 3, 4].map(() => mesh(new THREE.IcosahedronGeometry(0.2, 0), MF(0xF2F2F2, { transparent: true, opacity: 0.8 }), scene, false));

// ---------- props: rain, drip, flakes, ! ----------
const RAIN_N = 1300;
const rain = new THREE.InstancedMesh(new THREE.BoxGeometry(0.012, 0.28, 0.012), new THREE.MeshBasicMaterial({ color: 0xE6F0F8, transparent: true, opacity: 0.65 }), RAIN_N);
rain.frustumCulled = false; scene.add(rain);
const DRIP_N = 14;
const drip = new THREE.InstancedMesh(new THREE.SphereGeometry(0.035, 6, 6), M(0x8CC6EC, { roughness: 0.1 }), DRIP_N);
drip.frustumCulled = false; scene.add(drip);
const FLAKE_N = 90;
const flakes = new THREE.InstancedMesh(new THREE.OctahedronGeometry(0.03, 0), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9 }), FLAKE_N);
flakes.frustumCulled = false; scene.add(flakes);
let bang = null;
async function loadFont() {
  const json = await (await fetch('/node_modules/three/examples/fonts/helvetiker_bold.typeface.json')).json();
  const font = new FontLoader().parse(json);
  const g = new TextGeometry('!', { font, size: 0.4, depth: 0.1, curveSegments: 4, bevelEnabled: false }); g.center();
  bang = mesh(g, M(0xF2A93B, { emissive: 0xF2A93B, emissiveIntensity: 0.3 }), scene, false); bang.visible = false;
}

// =====================================================================
// TIMELINE
// =====================================================================
const rainAmount = t => Math.max(prog(t, 6.15, 6.6) * (1 - prog(t, 8.0, 8.4)), prog(t, 18.2, 18.6) * (1 - prog(t, 20.5, 20.9)), 0.65 * prog(t, 28.3, 28.8));

function charXZ(t) {
  return kf(t, [
    [0, [-3.8, 3.65]], [2.4, [-1.3, 3.65], E.lin], [4.0, [-1.3, 3.65]], [4.35, [-1.15, 2.95], E.io],
    [5.5, [-1.15, 2.95]], [5.95, [-0.5, 0.75], E.io], [7.0, [-0.5, 0.75]], [7.3, [-2.0, 2.6], E.out], [8.0, [-2.1, 2.7]],
    [12.0, [-2.1, 2.7]], [12.45, [0, 2.3], E.io], [12.9, [0, 0.4], E.lin], [13.25, [0, 0.4]], [13.85, [0, 2.3], E.lin],
    [16.0, [0, 2.3]], [16.4, [-2.0, 2.6], E.io], [17.85, [-2.0, 2.6]], [18.3, [0, 1.12], E.io],
    [20.0, [0, 1.12]], [20.5, [1.9, 2.7], E.io], [22.4, [1.9, 2.7]], [22.75, [0.95, 1.95], E.io],
    [23.45, [0.95, 1.95]], [23.85, [1.0, 2.75], E.io], [24.6, [1.0, 2.75]], [25.3, [0, 2.25], E.io],
    [27.45, [0, 2.25]], [28.05, [0, 0.5], E.lin],
  ]);
}
function charYaw(t) {
  return kf(t, [
    [0, 0.85], [2.35, 0.85], [2.6, 0], [4.0, 0], [4.15, 2.6], [5.5, 2.6], [5.6, 2.9], [5.85, 2.9], [6.05, 0.2],
    [7.0, 0.2], [7.15, 0.35], [8.2, 0.35], [8.4, 1.1], [10.9, 1.1], [11.05, 0.4],
    [12.0, 0.4], [12.15, 1.7], [12.35, 1.7], [12.5, Math.PI], [13.0, Math.PI], [13.2, 0],
    [16.0, 0], [16.1, -1.4], [16.3, -1.4], [16.5, -0.8], [17.85, -0.8], [17.95, 2.2], [18.15, 2.2], [18.35, 0],
    [20.0, 0], [20.1, 0.85], [20.4, 0.85], [20.55, -0.6], [22.4, -0.6], [22.5, -2.2], [22.65, -2.2], [22.8, -Math.PI],
    [23.45, -Math.PI], [23.85, 0], [24.6, 0], [24.75, -2.05], [25.2, -2.05], [25.35, -Math.PI], [25.8, -Math.PI], [26.0, 0],
    [27.2, 0], [27.4, -Math.PI],
  ]);
}
const EXPR = [[0, 'cold'], [2.4, 'idea'], [4.0, 'focus'], [5.9, 'happy'], [6.35, 'worried'], [7.0, 'shock'], [8.2, 'focus'],
  [11.0, 'proud'], [12.0, 'happy'], [13.2, 'freeze'], [16.6, 'focus'], [17.3, 'happy'], [18.35, 'shock'], [18.9, 'oops'],
  [20.4, 'focus'], [23.4, 'happy']];
const POSES = [[0, 2.55, 'cold'], [2.55, 3.95, 'idea'], [4.35, 5.4, 'conduct'], [5.95, 6.35, 'cheer'], [6.4, 7.0, 'lookup'],
  [7.0, 8.0, 'shock'], [8.3, 10.95, 'conduct'], [11.0, 12.0, 'proud'], [13.85, 15.95, 'cold'], [16.5, 17.3, 'conduct'],
  [17.35, 17.8, 'proud'], [18.35, 18.85, 'lookup'], [18.9, 19.85, 'facepalm'], [20.55, 21.2, 'lookup'], [21.25, 22.3, 'conduct'],
  [22.85, 23.3, 'tap'], [23.9, 24.6, 'present'], [26.0, 27.2, 'wave']];
function poseValues(name, t) {
  const p = { lx: 0, lz: 0, rx: 0, rz: 0, head: 0 };
  switch (name) {
    case 'cold': { const w = Math.sin(t * 22) * 0.12; Object.assign(p, { lx: -1.3 + w, lz: 0.8, rx: -1.3 - w, rz: -0.8, head: 0.12 }); break; }
    case 'idea': Object.assign(p, { rx: -0.3, rz: 2.75 + Math.sin(t * 6) * 0.08, lz: -0.12, head: -0.08 }); break;
    case 'conduct': Object.assign(p, { lx: -1.5 + 0.35 * Math.sin(t * 5), rx: -1.5 + 0.35 * Math.sin(t * 5 + 1.6), lz: -0.35, rz: 0.35, head: -0.12 }); break;
    case 'cheer': Object.assign(p, { lz: -2.6, rz: 2.6, head: -0.15 }); break;
    case 'lookup': Object.assign(p, { lz: -0.2, rz: 0.2, head: -0.5 }); break;
    case 'shock': Object.assign(p, { lz: -1.9, rz: 1.9, lx: -0.3, rx: -0.3, head: -0.1 }); break;
    case 'proud': Object.assign(p, { lz: -0.5, rz: 0.5, lx: 0.3, rx: 0.3, head: -0.12 }); break;
    case 'facepalm': Object.assign(p, { rx: -2.5, rz: -0.5, head: 0.3 }); break;
    case 'tap': { const k = Math.max(0, Math.sin((t - 22.85) * 14)); Object.assign(p, { rx: -1.45 - 0.2 * k, rz: -0.1 }); break; }
    case 'present': Object.assign(p, { lz: -1.1, rz: 1.1, lx: -0.35, rx: -0.35, head: -0.1 }); break;
    case 'wave': Object.assign(p, { rz: 2.55 + Math.sin(t * 13) * 0.35, rx: -0.2, head: -0.08 }); break;
  }
  return p;
}
function poseAt(t) {
  const acc = { lx: 0, lz: 0, rx: 0, rz: 0, head: 0 }; let ws = 0;
  for (const [s, e, n] of POSES) {
    if (t < s || t > e) continue;
    const w = Math.min(E.io(prog(t, s, s + 0.16)), 1 - E.io(prog(t, e - 0.16, e)));
    const v = poseValues(n, t);
    for (const k in acc) acc[k] += v[k] * w;
    ws += w;
  }
  return { ...acc, w: Math.min(1, ws) };
}
const BLINKS = [1.3, 4.7, 9.7, 11.6, 15.2, 17.6, 21.9, 24.2, 27.0];
const SKIN = new THREE.Color(COL.skin), SKIN_COLD = new THREE.Color(0xC9D9EC);
function applyExpression(t) {
  let ex = 'focus';
  for (const [s, n] of EXPR) if (t >= s) ex = n;
  const m = ch.m;
  for (const k in m) m[k].visible = false;
  let eyeSY = 1, eyeS = 1, happy = false, bl = 0, br = 0, by = 0.11;
  ch.mouth.scale.set(1, 1, 1);
  switch (ex) {
    case 'cold': case 'freeze': m.flat.visible = true; eyeSY = 0.55; bl = -0.35; br = 0.35; ch.mouth.scale.set(1, 1 + Math.sin(t * 40) * 0.8, 1); break;
    case 'idea': m.grin.visible = true; eyeS = 1.3; by = 0.13; break;
    case 'focus': m.smile.visible = true; break;
    case 'happy': case 'proud': m.grin.visible = true; happy = true; by = 0.125; break;
    case 'worried': m.flat.visible = true; bl = -0.3; br = 0.3; break;
    case 'shock': m.o.visible = true; eyeS = 1.35; by = 0.14; break;
    case 'oops': m.frown.visible = true; eyeSY = 0.65; bl = -0.4; br = 0.4; break;
  }
  const blink = BLINKS.some(b => t >= b && t < b + 0.12);
  ch.eyes.forEach(e => { e.visible = !happy; e.scale.set(eyeS, eyeS * (blink ? 0.12 : eyeSY), 1); });
  ch.arcs.forEach(a => { a.visible = happy; });
  ch.brows[0].rotation.z = bl; ch.brows[1].rotation.z = br;
  ch.brows.forEach(b => { b.position.y = by; });
  const fr = prog(t, 13.2, 13.5) * (1 - prog(t, 16.5, 17.0));
  ch.frost.visible = ch.frostSh.visible = fr > 0.01;
  ch.frost.scale.set(1, Math.max(0.01, fr), 1); ch.frostSh.scale.set(1, Math.max(0.01, fr), 1);
  ch.skin.color.copy(SKIN).lerp(SKIN_COLD, fr * 0.7);
}
function updateChar(t) {
  const [x, z] = charXZ(t), [x2, z2] = charXZ(t + 0.04);
  const moving = clamp(Math.hypot(x2 - x, z2 - z) / 0.04 / 1.2, 0, 1);
  ch.root.position.set(x, 0.06, z);
  ch.root.rotation.y = charYaw(t);
  ch.root.visible = t < 28.1;
  const ph = t * 13;
  ch.legs[0].rotation.x = Math.sin(ph) * 0.6 * moving;
  ch.legs[1].rotation.x = -Math.sin(ph) * 0.6 * moving;
  const pose = poseAt(t);
  const sw = Math.sin(ph) * 0.5 * moving * (1 - pose.w);
  ch.arms[0].rotation.set(pose.lx + sw, 0, pose.lz - 0.06 * (1 - pose.w));
  ch.arms[1].rotation.set(pose.rx - sw, 0, pose.rz + 0.06 * (1 - pose.w));
  ch.head.rotation.x = pose.head;
  const hop = (a, b, h) => (t > a && t < b ? Math.sin(Math.PI * (t - a) / (b - a)) * h : 0);
  ch.root.position.y += Math.abs(Math.sin(ph)) * 0.05 * moving + hop(5.97, 6.15, 0.3) + hop(6.17, 6.35, 0.26) + hop(7.0, 7.3, 0.35)
    + hop(11.05, 11.27, 0.14) + hop(17.35, 17.55, 0.14) + hop(23.45, 23.68, 0.15) + hop(26.05, 26.3, 0.12);
  const shiver = Math.max(1 - prog(t, 2.3, 2.6), prog(t, 13.3, 13.5) * (1 - prog(t, 15.8, 16.1)));
  ch.body.position.x = Math.sin(t * 57) * 0.018 * shiver;
  ch.body.rotation.z = Math.sin(t * 31) * 0.03 * shiver;
  applyExpression(t);
}

const m4 = new THREE.Matrix4(), qq = new THREE.Quaternion(), pp = new THREE.Vector3(), ss = new THREE.Vector3(), ee = new THREE.Euler();
const PLASTERED = new THREE.Color(0xF1EADD);
function updateHouse(t) {
  parts.forEach(p => updatePart(p, t));
  const ph = kf(t, [[4.95, 0], [5.3, 2.3, E.back], [8.15, 2.3], [8.45, H, E.out]]);
  const pc = prog(t, 16.95, 17.6);
  posts.forEach(p => {
    p.visible = ph > 0.01;
    p.scale.set(1, Math.max(0.01, ph), 1);
    p.position.y = BASE + ph / 2;
    p.material.color.setHex(COL.concrete).lerp(PLASTERED, pc);
  });
  const total = brickList.length;
  brickList.forEach((b, i) => {
    const w = WALLS[b.wi];
    const tj = 8.35 + (i / total) * 2.0;
    const appear = E.back(prog(t, tj - 0.4, tj - 0.25));
    const k = E.out(prog(t, tj, tj + 0.32));
    pp.copy(w.c).addScaledVector(w.a, b.u); pp.y = BASE + b.v;
    const r = hash(i + 7);
    pp.addScaledVector(w.n, (1 - k) * (1.6 + r)); pp.y += (1 - k) * (0.6 + hash(i + 3) * 1.2);
    ee.set((1 - k) * (r - 0.5) * 3, (1 - k) * (hash(i + 11) - 0.5) * 3, (1 - k) * (hash(i + 13) - 0.5) * 3);
    qq.setFromEuler(ee);
    const sc = t < tj - 0.4 ? 0.0001 : Math.max(0.0001, appear);
    const bw = b.bw * 0.94, bh = H / ROWS * 0.9;
    if (Math.abs(w.a.x) > 0.5) ss.set(bw * sc, bh * sc, T * sc); else ss.set(T * sc, bh * sc, bw * sc);
    m4.compose(pp, qq, ss); bricks.setMatrixAt(i, m4);
  });
  bricks.instanceMatrix.needsUpdate = true;
  plasterParts.forEach(({ m, t0, s, p, hh }) => {
    const k = E.out(prog(t, t0, t0 + 0.35));
    m.visible = k > 0.001;
    m.scale.set(s.x, Math.max(0.001, s.y * k), s.z);
    m.position.set(p.x, p.y - hh / 2 * (1 - k), p.z);
  });
  card.visible = t >= 5.2 && t < 8.6;
  if (card.visible) {
    const drop = E.bounce(prog(t, 5.35, 5.65));
    const sag = kf(t, [[6.4, 0], [7.05, 0.12, E.io], [7.32, 0.93, E.in]]);
    const fly = E.in(prog(t, 8.05, 8.55));
    card.position.set(fly * 4, BASE + 2.32 + (1 - drop) * 2.5 + fly * 2.5, 0);
    card.rotation.z = -fly * 2.4;
    card.scale.setScalar(1 - fly * 0.7);
    cardHalves[0].rotation.z = sag; cardHalves[1].rotation.z = -sag;
    const wet = prog(t, 6.2, 7.0);
    cardMat.color.setRGB(1 - wet * 0.35, 1 - wet * 0.38, 1 - wet * 0.42);
  }
  doorHinge.rotation.y = kf(t, [[25.4, 0], [25.8, -1.75, E.out], [28.0, -1.75], [28.3, 0, E.in]]);
  const lit = E.out(prog(t, 28.45, 28.75));
  doorLamp.material.emissiveIntensity = lit * 2.4;
  glassMat.emissiveIntensity = lit * 1.4;
  glassMat.color.setHex(COL.glass).lerp(new THREE.Color(0xFFE2A0), lit);
  windows[1].rotation.z = kf(t, [[0, 0.32], [23.0, 0.32], [23.5, 0, E.elastic]]);
  const pr = kf(t, [[18.5, 0], [20.0, 0.5, E.out], [20.6, 0.5], [21.2, 0, E.in]]);
  puddle.visible = pr > 0.01; puddle.scale.set(pr, 1, pr * 0.8); puddle.position.set(0, BASE + 0.035, 0.95);
  smoke.forEach((s, i) => {
    const f = ((t - 28.6) * 0.55 + i / 5) % 1;
    s.visible = t > 28.6 + i * 0.25;
    s.position.set(1.05 + f * 0.6, ROOF_Y + RISE * 0.72 + 1.0 + f * 1.6, -0.6);
    s.scale.setScalar(0.5 + f * 1.4); s.material.opacity = 0.8 * (1 - f);
  });
}

const ONE = V3(1, 1, 1), ZERO = V3(0, 0, 0), DROP_S = V3(1, 1.6, 1), CLOUD_RAIN = new THREE.Color(0x9AA6B2);
function updateWeather(t) {
  const amt = rainAmount(t);
  qq.setFromEuler(ee.set(0, 0, 0.1));
  for (let i = 0; i < RAIN_N; i++) {
    const hx = hash(i), hz = hash(i + 1000), hy = hash(i + 2000), hv = hash(i + 3000);
    const x = -7 + hx * 14, z = -5 + hz * 13;
    const y = 11 - ((t * (10 + hv * 3) + hy * 11) % 11);
    let vis = hv < amt && y > 0.12;
    if (vis && t >= 5.6 && t < 7.05 && Math.abs(x) < 1.75 && Math.abs(z) < 1.5 && y < BASE + 2.4) vis = false;
    if (vis && t >= 11.2 && Math.abs(x) < RW / 2 && Math.abs(z) < RD / 2 && y < ROOF_Y + RISE * (1 - Math.abs(x) / (RW / 2)) + 0.3) vis = false;
    pp.set(x - y * 0.1, y, z);
    m4.compose(pp, qq, vis ? ONE : ZERO); rain.setMatrixAt(i, m4);
  }
  rain.instanceMatrix.needsUpdate = true; rain.visible = amt > 0.001;
  drip.visible = t >= 18.35 && t < 20.15;
  qq.identity();
  for (let i = 0; i < DRIP_N; i++) {
    const top = ROOF_Y - 0.05, bottom = BASE + 1.95;
    const y = top - ((Math.max(0, t - 18.35) * 3.2 + i / DRIP_N) % 1) * (top - bottom);
    pp.set((hash(i) - 0.5) * 0.12, y, 1.08 + (hash(i + 4) - 0.5) * 0.08);
    m4.compose(pp, qq, DROP_S); drip.setMatrixAt(i, m4);
  }
  drip.instanceMatrix.needsUpdate = true;
  const f1 = 1 - prog(t, 3.8, 4.5), f2 = prog(t, 12.6, 12.8) * (1 - prog(t, 13.4, 13.7));
  const fa = Math.max(f1, f2);
  flakes.visible = fa > 0.01; flakes.material.opacity = 0.9 * fa;
  for (let i = 0; i < FLAKE_N; i++) {
    let x, y, z;
    if (f1 >= f2) { const sp = 1.8 + hash(i + 50) * 1.5; x = -7 + ((t * sp + hash(i + 70) * 10) % 10); y = 0.3 + hash(i + 90) * 3 + Math.sin(t * 2 + i) * 0.15; z = 2.2 + hash(i + 110) * 3; }
    else { const sp = 7 + hash(i + 50) * 4; x = -4 + ((t * sp + hash(i + 70) * 8) % 8); y = BASE + 0.3 + hash(i + 90) * 2.3; z = -1 + hash(i + 110) * 2.6; }
    m4.makeTranslation(x, y, z); flakes.setMatrixAt(i, m4);
  }
  flakes.instanceMatrix.needsUpdate = true;
  const cold = 1 - prog(t, 3.5, 5.0);
  skyMat.uniforms.top.value.copy(SKY.top).lerp(SKY.coldTop, cold * 0.7).lerp(SKY.rainTop, amt * 0.85);
  skyMat.uniforms.hor.value.copy(SKY.hor).lerp(SKY.coldHor, cold * 0.7).lerp(SKY.rainHor, amt * 0.85);
  scene.fog.color.copy(skyMat.uniforms.hor.value);
  sun.intensity = 2.6 - amt * 1.3;
  hemi.intensity = 1.35 - amt * 0.3;
  clouds.forEach(c => { const u = c.userData; c.position.set(u.x + t * 0.25, u.y, u.z); c.children.forEach(k => k.material.color.setHex(0xffffff).lerp(CLOUD_RAIN, amt)); });
}

function updateFx(t) {
  if (!bang) return;
  const head = new THREE.Vector3(); ch.head.getWorldPosition(head);
  bang.visible = t >= 2.45 && t < 3.85;
  const s = E.back(prog(t, 2.45, 2.7)) * (1 - E.in(prog(t, 3.7, 3.85)));
  bang.scale.setScalar(Math.max(0.001, s));
  bang.position.copy(head).add(V3(0.3, 0.75 + Math.sin(t * 6) * 0.04, 0));
  bang.quaternion.copy(camera.quaternion); bang.rotateZ(Math.sin(t * 8) * 0.12);
}

const CAM = [
  [0.0, [-3.6, 1.6, 7.2], [-3.7, 1.15, 3.6]],
  [2.4, [-1.4, 1.65, 6.9], [-1.3, 1.2, 3.6]],
  [3.7, [-1.3, 1.95, 6.6], [-1.3, 1.75, 3.6]],
  [4.6, [0.3, 3.4, 11.2], [-0.3, 1.3, 0.8]],
  [7.9, [0.0, 3.2, 10.6], [-0.4, 1.2, 0.8]],
  [8.6, [1.2, 4.3, 13.2], [0, 2.1, 0]],
  [11.9, [0.8, 4.1, 12.6], [0, 2.2, 0]],
  [12.6, [1.4, 2.9, 10.6], [0, 1.7, 0.8]],
  [15.9, [1.1, 2.3, 8.0], [0, 1.3, 1.6]],
  [16.6, [-1.6, 3.7, 12.2], [-0.2, 2.0, 0.3]],
  [17.9, [0.4, 2.2, 6.9], [0, 1.5, 1.2]],
  [19.9, [0.3, 2.1, 6.2], [0, 1.6, 1.2]],
  [20.7, [1.8, 4.5, 13.0], [0.2, 2.5, 0]],
  [22.4, [1.2, 3.5, 11.4], [0.4, 2.0, 0.6]],
  [24.5, [0.7, 3.3, 10.8], [0.3, 2.0, 0.6]],
  [30.0, [0.0, 3.6, 15.0], [0, 1.9, 0]],
];
const CAM_P = CAM.map(([tt, p]) => [tt, p, E.io]), CAM_T = CAM.map(([tt, , g]) => [tt, g, E.io]);
function updateCamera(t) {
  camera.position.set(...kf(t, CAM_P));
  camera.lookAt(V3(...kf(t, CAM_T)));
  camera.updateMatrixWorld();
}

function renderAt(t) {
  updateCamera(t);
  updateHouse(t);
  updateChar(t);
  updateWeather(t);
  updateFx(t);
  renderer.render(scene, camera);
}
window.renderAt = (t, q = 0.93) => { renderAt(t); return renderer.domElement.toDataURL('image/jpeg', q); };
window.ready = loadFont().then(() => { renderAt(0); return true; });
