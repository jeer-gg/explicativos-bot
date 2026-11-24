// Dibujos 2D de la técnica 2.5D: todo lo orgánico (manos, personas, agua, humo, fuego,
// plantas...) se dibuja con curvas en un lienzo y se pone como "recorte" dentro del mundo 3D.
// Son funciones puras de canvas: (contexto, ancho, alto, opciones). Sin dependencias.

export type Colores = {
  piel: string;
  pielSombra: string;
  ropa: string;
  ropaSombra: string;
  principal: string;
  resalte: string;
  agua: string;
  aguaClara: string;
  contorno: string;
  claro: string;
};

export type Opc = {
  t: number; // segundos
  c: Colores;
  contorno: boolean; // false en el estilo plastilina
  pose?: string;
  nivel?: number; // 0 a 1 (agua)
  fuga?: [number, number] | null; // punto (u, v) hacia donde se escapa el agua, 0 a 1
  fuerza?: number; // 0 a 1 (intensidad del efecto)
  color?: string; // color propio del dibujo (persona, efecto)
};

export type Dibujo = (x: CanvasRenderingContext2D, w: number, h: number, o: Opc) => void;

// ---------- utilidades ----------
const grosor = (o: Opc, k = 1) => (o.contorno ? 13 * k : 0);

function trazo(x: CanvasRenderingContext2D, o: Opc, relleno: string, k = 1) {
  x.fillStyle = relleno;
  x.fill();
  if (o.contorno) {
    x.lineWidth = grosor(o, k);
    x.strokeStyle = o.c.contorno;
    x.lineJoin = 'round';
    x.lineCap = 'round';
    x.stroke();
  }
}

/** Miembro redondeado (brazo, pierna): contorno ancho debajo y color encima. */
function miembro(x: CanvasRenderingContext2D, o: Opc, puntos: [number, number][], ancho: number, color: string) {
  const camino = () => {
    x.beginPath();
    puntos.forEach(([a, b], i) => (i ? x.lineTo(a, b) : x.moveTo(a, b)));
  };
  x.lineJoin = 'round';
  x.lineCap = 'round';
  if (o.contorno) {
    camino();
    x.strokeStyle = o.c.contorno;
    x.lineWidth = ancho + grosor(o) * 1.6;
    x.stroke();
  }
  camino();
  x.strokeStyle = color;
  x.lineWidth = ancho;
  x.stroke();
}

/** Brillo suave (estilo plastilina) o reflejo de dibujo. */
function reflejo(x: CanvasRenderingContext2D, o: Opc, cx: number, cy: number, rx: number, ry: number, giro = -0.5) {
  x.save();
  x.globalAlpha = o.contorno ? 0.5 : 0.35;
  x.fillStyle = '#FFFFFF';
  x.beginPath();
  x.ellipse(cx, cy, rx, ry, giro, 0, Math.PI * 2);
  x.fill();
  x.restore();
}

const escalar = (x: CanvasRenderingContext2D, w: number, h: number, base = 512) => {
  x.save();
  x.scale(w / base, h / base);
};

// ---------- manos (mirando a la izquierda, la manga sale por la derecha) ----------
function manga(x: CanvasRenderingContext2D, o: Opc) {
  x.beginPath();
  x.moveTo(336, 176);
  x.bezierCurveTo(400, 160, 470, 148, 512, 146);
  x.lineTo(512, 336);
  x.bezierCurveTo(460, 336, 400, 334, 338, 328);
  x.closePath();
  trazo(x, o, o.c.ropa);
  x.beginPath();
  x.moveTo(346, 300);
  x.bezierCurveTo(400, 304, 460, 306, 512, 306);
  x.lineTo(512, 330);
  x.bezierCurveTo(460, 330, 400, 328, 346, 324);
  x.closePath();
  x.fillStyle = o.c.ropaSombra;
  x.fill();
}

function palma(x: CanvasRenderingContext2D, o: Opc) {
  x.beginPath();
  x.moveTo(344, 186);
  x.bezierCurveTo(300, 150, 214, 160, 184, 200);
  x.bezierCurveTo(160, 236, 170, 300, 212, 322);
  x.bezierCurveTo(262, 346, 322, 336, 348, 320);
  x.closePath();
  trazo(x, o, o.c.piel);
}

function dedo(x: CanvasRenderingContext2D, o: Opc, y: number, largo: number, doblado = 0) {
  // dedo que sale de la palma hacia la izquierda; doblado 0 = recto, 1 = cerrado
  const l = largo * (1 - 0.55 * doblado);
  x.beginPath();
  x.moveTo(212, y);
  x.bezierCurveTo(212 - l * 0.6, y - 9, 212 - l, y + 4 + doblado * 10, 212 - l, y + 24 + doblado * 8);
  x.bezierCurveTo(212 - l, y + 44, 212 - l * 0.6, y + 48, 212, y + 40);
  x.closePath();
  trazo(x, o, o.c.piel);
  if (o.contorno && l > 60) {
    x.beginPath();
    x.moveTo(212 - l * 0.55, y + 8);
    x.quadraticCurveTo(212 - l * 0.6, y + 22, 212 - l * 0.55, y + 34);
    x.strokeStyle = o.c.pielSombra;
    x.lineWidth = 5;
    x.stroke();
  }
}

function pulgar(x: CanvasRenderingContext2D, o: Opc, arriba = true) {
  x.beginPath();
  if (arriba) {
    x.moveTo(248, 192);
    x.bezierCurveTo(214, 150, 152, 140, 122, 160);
    x.bezierCurveTo(100, 176, 120, 198, 152, 194);
    x.bezierCurveTo(188, 192, 208, 202, 230, 218);
  } else {
    x.moveTo(250, 300);
    x.bezierCurveTo(220, 340, 170, 350, 150, 334);
    x.bezierCurveTo(134, 320, 150, 302, 178, 302);
    x.bezierCurveTo(200, 302, 220, 296, 236, 286);
  }
  x.closePath();
  trazo(x, o, o.c.piel);
}

const manoAgarra: Dibujo = (x, w, h, o) => {
  escalar(x, w, h);
  manga(x, o);
  palma(x, o);
  dedo(x, o, 206, 118, 0.15);
  dedo(x, o, 246, 126, 0.15);
  dedo(x, o, 286, 110, 0.15);
  x.fillStyle = o.c.pielSombra;
  x.beginPath();
  x.ellipse(258, 298, 52, 14, 0, 0, Math.PI * 2);
  x.fill();
  pulgar(x, o, true);
  reflejo(x, o, 286, 196, 34, 10, -0.15);
  x.restore();
};

const manoSenala: Dibujo = (x, w, h, o) => {
  escalar(x, w, h);
  manga(x, o);
  palma(x, o);
  dedo(x, o, 246, 96, 1);
  dedo(x, o, 284, 90, 1);
  pulgar(x, o, false);
  // índice extendido
  x.beginPath();
  x.moveTo(214, 196);
  x.bezierCurveTo(160, 188, 90, 190, 54, 198);
  x.bezierCurveTo(28, 204, 28, 236, 54, 238);
  x.bezierCurveTo(100, 240, 160, 236, 212, 236);
  x.closePath();
  trazo(x, o, o.c.piel);
  reflejo(x, o, 120, 204, 40, 6, 0);
  x.restore();
};

const manoAbierta: Dibujo = (x, w, h, o) => {
  // palma de frente, dedos hacia arriba, muñeca abajo
  escalar(x, w, h);
  x.beginPath();
  x.moveTo(176, 512);
  x.lineTo(186, 400);
  x.lineTo(326, 400);
  x.lineTo(336, 512);
  x.closePath();
  trazo(x, o, o.c.ropa);
  const dedos: [number, number, number][] = [[192, 118, -0.2], [232, 142, -0.06], [276, 140, 0.07], [318, 116, 0.2]];
  for (const [dx, largo, giro] of dedos) {
    x.save();
    x.translate(dx, 300);
    x.rotate(giro);
    x.beginPath();
    x.moveTo(-21, 10);
    x.lineTo(-21, -largo);
    x.arc(0, -largo, 21, Math.PI, 0);
    x.lineTo(21, 10);
    x.closePath();
    trazo(x, o, o.c.piel);
    x.restore();
  }
  x.beginPath();
  x.moveTo(170, 290);
  x.bezierCurveTo(160, 360, 190, 420, 256, 420);
  x.bezierCurveTo(322, 420, 352, 360, 344, 290);
  x.bezierCurveTo(300, 270, 214, 270, 170, 290);
  x.closePath();
  trazo(x, o, o.c.piel);
  x.beginPath();
  x.moveTo(176, 330);
  x.bezierCurveTo(130, 300, 96, 260, 104, 236);
  x.bezierCurveTo(114, 214, 150, 236, 186, 286);
  x.closePath();
  trazo(x, o, o.c.piel);
  x.strokeStyle = o.c.pielSombra;
  x.lineWidth = 6;
  x.beginPath();
  x.moveTo(214, 360);
  x.quadraticCurveTo(256, 384, 300, 352);
  x.stroke();
  x.restore();
};

// ---------- persona sin cara (de cuerpo entero, alto = 2 x ancho) ----------
const persona: Dibujo = (x, w, h, o) => {
  // Persona sin cara con articulaciones (cadera, rodilla, hombro, codo) para que camine natural:
  // piernas y brazos opuestos, rodilla que se dobla al avanzar, cuerpo que sube y baja un poco.
  // Camina hacia la DERECHA (con espejo, hacia la izquierda). Quieta, solo respira.
  x.save();
  x.scale(w / 256, h / 512);
  const pose = o.pose || 'parado';
  const ropa = o.color || o.c.ropa;
  const t = o.t;
  const camina = pose === 'camina';
  const fase = t * 5.4; // ~0,86 pasos completos por segundo: ritmo de caminar tranquilo
  const rebote = camina ? -Math.abs(Math.sin(fase)) * 7 + 3 : Math.sin(t * 2.2) * 1.5;
  x.translate(0, rebote);
  const L = 34;
  const pierna = (cx: number, desfase: number): [number, number][] => {
    const f = fase + desfase;
    const muslo = camina ? 0.42 * Math.sin(f) : 0;
    const rodilla = camina ? 0.85 * Math.max(0, Math.cos(f)) : 0;
    const k: [number, number] = [cx + Math.sin(muslo) * 80, 332 + Math.cos(muslo) * 80];
    const p: [number, number] = [k[0] + Math.sin(muslo - rodilla) * 78, k[1] + Math.cos(muslo - rodilla) * 78];
    return [[cx, 332], k, p];
  };
  const brazo = (cx: number, desfase: number): [number, number][] => {
    const f = fase + desfase;
    const hombro = camina ? -0.38 * Math.sin(f) : Math.sin(t * 1.5 + desfase) * 0.03;
    const codo = camina ? 0.25 + 0.25 * Math.max(0, -Math.sin(f)) : 0.12;
    const c: [number, number] = [cx + Math.sin(hombro) * 64, 202 + Math.cos(hombro) * 64];
    const m: [number, number] = [c[0] + Math.sin(hombro + codo) * 60, c[1] + Math.cos(hombro + codo) * 60];
    return [[cx, 202], c, m];
  };
  const zapato = (pie: [number, number]) => {
    x.beginPath();
    x.ellipse(pie[0] + 9, Math.min(pie[1] + 6, 500), 26, 12, 0, 0, Math.PI * 2);
    trazo(x, o, o.c.contorno === '#1B1B1F' ? '#3A3A44' : o.c.contorno, 0.6);
  };
  // lado de atrás (más oscuro, para que se lean las dos piernas y los dos brazos)
  const piernaAtras = pierna(122, Math.PI), piernaAdelante = pierna(134, 0);
  let brazoAtras = brazo(112, 0), brazoAdelante = brazo(144, Math.PI);
  if (pose === 'senala') brazoAdelante = [[144, 202], [196, 186], [246, 172]];
  if (pose === 'piensa') brazoAdelante = [[144, 202], [176, 262], [146, 150]];
  if (pose === 'sorprendida') {
    brazoAtras = [[112, 202], [76, 150], [70, 100]];
    brazoAdelante = [[144, 202], [182, 150], [188, 100]];
  }
  miembro(x, o, brazoAtras, L * 0.82, oscurecerHex(ropa, 0.8));
  miembro(x, o, piernaAtras, L, oscurecerHex(o.c.ropaSombra, 0.85));
  zapato(piernaAtras[2]);
  miembro(x, o, piernaAdelante, L, o.c.ropaSombra);
  zapato(piernaAdelante[2]);
  // cuerpo (un poco inclinado hacia adelante al caminar)
  x.save();
  if (camina) {
    x.translate(128, 330);
    x.rotate(0.05);
    x.translate(-128, -330);
  }
  x.beginPath();
  x.moveTo(92, 186);
  x.bezierCurveTo(100, 170, 156, 170, 164, 186);
  x.bezierCurveTo(176, 240, 172, 300, 166, 344);
  x.bezierCurveTo(140, 354, 116, 354, 90, 344);
  x.bezierCurveTo(82, 300, 80, 240, 92, 186);
  x.closePath();
  trazo(x, o, ropa);
  reflejo(x, o, 114, 222, 14, 28, 0.2);
  x.beginPath();
  x.rect(117, 150, 22, 26);
  trazo(x, o, o.c.pielSombra, 0.7);
  x.beginPath();
  x.ellipse(130, 112, 42, 48, 0, 0, Math.PI * 2);
  trazo(x, o, o.c.piel);
  reflejo(x, o, 114, 92, 13, 8);
  x.restore();
  miembro(x, o, brazoAdelante, L * 0.82, ropa);
  for (const pm of [brazoAtras[2], brazoAdelante[2]]) {
    x.beginPath();
    x.arc(pm[0], pm[1], 14, 0, Math.PI * 2);
    trazo(x, o, o.c.piel, 0.8);
  }
  x.restore();
};

function oscurecerHex(hex: string, k: number): string {
  if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return hex;
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v * k));
  return '#' + c.map((v) => v.toString(16).padStart(2, '0')).join('');
}

// ---------- agua (cuerpo de agua con superficie animada) ----------
const agua: Dibujo = (x, w, h, o) => {
  const t = o.t;
  const nivel = o.nivel ?? 0.75;
  const arriba = h * (1 - nivel);
  const ola = (u: number) => arriba + Math.sin(u * 22 + t * 4) * h * 0.012 + Math.sin(u * 9 - t * 2) * h * 0.008;
  x.beginPath();
  x.moveTo(0, h);
  for (let i = 0; i <= 48; i++) x.lineTo((i / 48) * w, ola(i / 48));
  x.lineTo(w, h);
  x.closePath();
  x.fillStyle = o.c.agua;
  x.globalAlpha = 0.9;
  x.fill();
  x.globalAlpha = 1;
  // franja más oscura al fondo
  const g = x.createLinearGradient(0, arriba, 0, h);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(0,40,90,0.18)');
  x.fillStyle = g;
  x.fill();
  x.beginPath();
  for (let i = 0; i <= 48; i++) (i ? x.lineTo : x.moveTo).call(x, (i / 48) * w, ola(i / 48));
  x.strokeStyle = o.c.aguaClara;
  x.lineWidth = Math.max(4, h * 0.022);
  x.stroke();
  x.strokeStyle = 'rgba(255,255,255,0.35)';
  x.lineWidth = Math.max(3, h * 0.012);
  for (let k = 0; k < 4; k++) {
    const y = arriba + h * (0.12 + k * 0.14);
    if (y < h - 8) {
      x.beginPath();
      x.moveTo(w * (0.1 + k * 0.07), y);
      x.lineTo(w * (0.26 + k * 0.07), y);
      x.stroke();
    }
  }
  if (o.fuga) {
    const [fu, fv] = o.fuga;
    const cx = fu * w, cy = h * (1 - fv);
    const f0 = o.fuerza ?? 1;
    for (let k = 0; k < 18; k++) {
      const f = (t * 0.55 + k / 18) % 1;
      const ang = k * 2.4 + f * 3;
      const r = (1 - f) * Math.min(w, h) * 0.42 + 6;
      const px = cx + Math.cos(ang) * r * 1.2, py = cy - Math.abs(Math.sin(ang)) * r * 0.8;
      if (py > arriba + 8 && px > 4 && px < w - 4) {
        x.fillStyle = `rgba(255,255,255,${0.9 * f0})`;
        x.beginPath();
        x.arc(px, py, (4 + 4 * (1 - f)) * (w / 256), 0, Math.PI * 2);
        x.fill();
      }
    }
    x.strokeStyle = `rgba(255,255,255,${0.75 * f0})`;
    x.lineWidth = 3 * (w / 256);
    for (let k = 0; k < 3; k++) {
      const f = (t * 0.8 + k / 3) % 1;
      x.beginPath();
      x.arc(cx, cy, (10 + f * 40) * (w / 256), Math.PI * 1.1, Math.PI * 1.9);
      x.stroke();
    }
  }
};

/** Chorro de agua que cae (de arriba hacia abajo). fuerza 0 a 1. */
const chorro: Dibujo = (x, w, h, o) => {
  const f = o.fuerza ?? 1;
  if (f <= 0.01) return;
  const t = o.t;
  const ancho = w * (0.12 + 0.22 * f);
  x.beginPath();
  x.moveTo(w / 2 - ancho * 0.4, 0);
  for (let i = 0; i <= 20; i++) {
    const v = i / 20;
    x.lineTo(w / 2 - ancho / 2 - Math.sin(v * 12 - t * 18) * w * 0.012, v * h);
  }
  for (let i = 20; i >= 0; i--) {
    const v = i / 20;
    x.lineTo(w / 2 + ancho / 2 + Math.sin(v * 11 - t * 16) * w * 0.012, v * h);
  }
  x.closePath();
  x.fillStyle = o.c.agua;
  x.globalAlpha = 0.85;
  x.fill();
  x.globalAlpha = 1;
  x.strokeStyle = 'rgba(255,255,255,0.7)';
  x.lineWidth = w * 0.02;
  for (let k = 0; k < 3; k++) {
    const y0 = ((t * 2.2 + k / 3) % 1) * h;
    x.beginPath();
    x.moveTo(w / 2 - ancho * 0.15, y0);
    x.lineTo(w / 2 - ancho * 0.15, Math.min(h, y0 + h * 0.12));
    x.stroke();
  }
};

// ---------- efectos ----------
function gotaForma(x: CanvasRenderingContext2D, cx: number, cy: number, r: number) {
  x.beginPath();
  x.moveTo(cx, cy - r * 1.8);
  x.bezierCurveTo(cx + r * 0.4, cy - r * 0.9, cx + r, cy - r * 0.3, cx + r, cy + r * 0.2);
  x.arc(cx, cy + r * 0.2, r, 0, Math.PI);
  x.bezierCurveTo(cx - r, cy - r * 0.3, cx - r * 0.4, cy - r * 0.9, cx, cy - r * 1.8);
  x.closePath();
}

const gotas: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  for (let k = 0; k < 3; k++) {
    const f = (o.t * 0.9 + k / 3) % 1;
    const y = 30 + f * f * 200;
    gotaForma(x, 128, y, 16);
    x.globalAlpha = f > 0.85 ? (1 - f) / 0.15 : 1;
    trazo(x, o, o.color || o.c.agua, 0.5);
    reflejo(x, o, 122, y - 4, 4, 7, 0.3);
    x.globalAlpha = 1;
  }
  x.restore();
};

const burbujas: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  for (let k = 0; k < 9; k++) {
    const f = (o.t * 0.5 + k / 9) % 1;
    const bx = 128 + Math.sin(k * 2.1 + o.t * 3) * 50 + (k % 3 - 1) * 30;
    const by = 240 - f * 230;
    const r = 6 + (k % 4) * 4;
    x.globalAlpha = Math.min(1, (1 - f) * 3);
    x.beginPath();
    x.arc(bx, by, r, 0, Math.PI * 2);
    x.fillStyle = 'rgba(255,255,255,0.25)';
    x.fill();
    x.strokeStyle = o.contorno ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.8)';
    x.lineWidth = 3;
    x.stroke();
    x.beginPath();
    x.arc(bx - r * 0.35, by - r * 0.35, r * 0.25, 0, Math.PI * 2);
    x.fillStyle = '#FFFFFF';
    x.fill();
  }
  x.globalAlpha = 1;
  x.restore();
};

const vapor: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  const color = o.color || '#FFFFFF';
  for (let k = 0; k < 3; k++) {
    const f = (o.t * 0.35 + k / 3) % 1;
    const bx = 80 + k * 48;
    x.globalAlpha = Math.sin(f * Math.PI) * 0.85;
    x.beginPath();
    for (let i = 0; i <= 24; i++) {
      const v = i / 24;
      const y = 250 - v * 220 - f * 30;
      const px = bx + Math.sin(v * 7 + o.t * 2 + k) * 14 * (0.4 + v);
      i ? x.lineTo(px, y) : x.moveTo(px, y);
    }
    x.strokeStyle = color;
    x.lineCap = 'round';
    x.lineWidth = 14 - f * 6;
    x.stroke();
  }
  x.globalAlpha = 1;
  x.restore();
};

const fuego: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  const capas: [string, number][] = [['#E8471F', 1], ['#F28C28', 0.75], ['#FFD34D', 0.5]];
  capas.forEach(([color, k], i) => {
    const temblor = Math.sin(o.t * 13 + i * 2) * 8 * k;
    x.beginPath();
    x.moveTo(128 - 90 * k, 240);
    x.bezierCurveTo(128 - 110 * k, 160, 128 - 40 * k + temblor, 120, 128 + temblor * 1.4, 240 - 220 * k);
    x.bezierCurveTo(128 + 50 * k + temblor, 130, 128 + 110 * k, 160, 128 + 90 * k, 240);
    x.closePath();
    trazo(x, {...o, contorno: o.contorno && i === 0}, color, 0.7);
  });
  x.restore();
};

const chispa: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  const pts: [number, number][] = [[40, 30], [120, 110], [90, 128], [200, 226], [140, 132], [170, 116], [96, 40]];
  const brillo = 0.75 + 0.25 * Math.sin(o.t * 40);
  x.globalAlpha = brillo;
  x.beginPath();
  pts.forEach(([a, b], i) => (i ? x.lineTo(a, b) : x.moveTo(a, b)));
  x.closePath();
  trazo(x, o, o.color || '#FFD34D', 0.7);
  x.beginPath();
  x.moveTo(70, 50);
  x.lineTo(126, 112);
  x.strokeStyle = '#FFFFFF';
  x.lineWidth = 8;
  x.stroke();
  x.globalAlpha = 1;
  x.restore();
};

const ondas: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  x.strokeStyle = o.color || o.c.resalte;
  x.lineCap = 'round';
  for (let k = 0; k < 3; k++) {
    const f = (o.t * 0.9 + k / 3) % 1;
    x.globalAlpha = 1 - f;
    x.lineWidth = 12 - f * 6;
    x.beginPath();
    x.arc(40, 128, 30 + f * 180, -0.7, 0.7);
    x.stroke();
  }
  x.globalAlpha = 1;
  x.restore();
};

const destello: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  const s = 0.75 + 0.25 * Math.sin(o.t * 8);
  x.translate(128, 128);
  x.scale(s, s);
  x.rotate(o.t * 0.8);
  x.beginPath();
  for (let i = 0; i < 8; i++) {
    const r = i % 2 === 0 ? 110 : 26;
    const a = (i / 8) * Math.PI * 2;
    i ? x.lineTo(Math.cos(a) * r, Math.sin(a) * r) : x.moveTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  x.closePath();
  trazo(x, o, o.color || '#FFE066', 0.6);
  x.restore();
};

const planta: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  const hojas: [number, number, number][] = [[-0.9, 80, 0], [-0.4, 100, 1], [0.1, 110, 0], [0.6, 96, 1], [1.0, 76, 0]];
  hojas.forEach(([ang, largo, tono]) => {
    x.save();
    x.translate(128, 170);
    x.rotate(ang + Math.sin(o.t * 1.5 + ang) * 0.04);
    x.beginPath();
    x.moveTo(0, 0);
    x.bezierCurveTo(-22, -largo * 0.4, -16, -largo * 0.9, 0, -largo);
    x.bezierCurveTo(16, -largo * 0.9, 22, -largo * 0.4, 0, 0);
    x.closePath();
    trazo(x, o, tono ? '#5DAA4A' : '#76C25B', 0.6);
    x.restore();
  });
  x.beginPath();
  x.moveTo(84, 168);
  x.lineTo(172, 168);
  x.lineTo(158, 246);
  x.lineTo(98, 246);
  x.closePath();
  trazo(x, o, o.color || '#D9733B', 0.7);
  x.restore();
};

const nube: Dibujo = (x, w, h, o) => {
  // nube de pensamiento con sus burbujitas
  escalar(x, w, h, 256);
  const c: [number, number, number][] = [[80, 100, 44], [128, 78, 54], [180, 100, 44], [160, 140, 40], [100, 142, 40]];
  x.beginPath();
  c.forEach(([a, b, r]) => {
    x.moveTo(a + r, b);
    x.arc(a, b, r, 0, Math.PI * 2);
  });
  trazo(x, o, o.color || '#FFFFFF', 0.8);
  x.fillStyle = o.color || '#FFFFFF';
  x.beginPath();
  x.ellipse(130, 112, 80, 40, 0, 0, Math.PI * 2);
  x.fill();
  for (const [a, b, r] of [[70, 196, 14], [50, 230, 9]] as [number, number, number][]) {
    x.beginPath();
    x.arc(a, b, r, 0, Math.PI * 2);
    trazo(x, o, o.color || '#FFFFFF', 0.6);
  }
  x.restore();
};

/** Cabeza de perfil en corte (sin cara): se ve el cerebro, que se ilumina con `fuerza`. */
const cabeza: Dibujo = (x, w, h, o) => {
  escalar(x, w, h, 256);
  x.beginPath();
  x.moveTo(84, 236);
  x.bezierCurveTo(80, 206, 70, 190, 56, 170);
  x.bezierCurveTo(40, 150, 38, 120, 44, 96);
  x.bezierCurveTo(56, 40, 110, 18, 150, 24);
  x.bezierCurveTo(206, 32, 226, 80, 222, 120);
  x.bezierCurveTo(220, 140, 230, 150, 236, 162);
  x.bezierCurveTo(240, 170, 230, 174, 224, 176);
  x.bezierCurveTo(226, 196, 214, 206, 196, 204);
  x.bezierCurveTo(188, 216, 180, 232, 182, 246);
  x.closePath();
  trazo(x, o, o.c.piel);
  // cerebro
  const f = o.fuerza ?? 0;
  x.beginPath();
  x.moveTo(66, 112);
  x.bezierCurveTo(64, 70, 104, 44, 142, 46);
  x.bezierCurveTo(186, 48, 206, 84, 198, 116);
  x.bezierCurveTo(192, 142, 160, 150, 128, 146);
  x.bezierCurveTo(96, 152, 68, 140, 66, 112);
  x.closePath();
  const base = o.color || '#F3A6B8';
  trazo(x, o, base, 0.7);
  if (f > 0) {
    x.save();
    x.globalAlpha = 0.65 * f;
    x.fillStyle = o.c.resalte;
    x.fill();
    x.restore();
  }
  x.strokeStyle = o.contorno ? o.c.contorno : 'rgba(0,0,0,0.18)';
  x.lineWidth = o.contorno ? 6 : 5;
  x.lineCap = 'round';
  const pliegues: [number, number, number, number, number, number][] = [
    [90, 80, 110, 70, 120, 90], [130, 60, 150, 76, 140, 96], [160, 90, 180, 86, 184, 110], [96, 120, 118, 110, 140, 124], [150, 120, 166, 132, 176, 122],
  ];
  for (const [a, b, c2, d, e, f2] of pliegues) {
    x.beginPath();
    x.moveTo(a, b);
    x.quadraticCurveTo(c2, d, e, f2);
    x.stroke();
  }
  x.restore();
};

export const DIBUJOS = {
  mano_agarra: manoAgarra,
  mano_senala: manoSenala,
  mano_abierta: manoAbierta,
  persona,
  agua,
  chorro,
  gotas,
  burbujas,
  vapor,
  fuego,
  chispa,
  ondas,
  destello,
  planta,
  nube,
  cabeza,
};

export type NombreDibujo = keyof typeof DIBUJOS;

export const COLORES_BASE: Colores = {
  piel: '#E8B68E',
  pielSombra: '#CF9A73',
  ropa: '#2FA4E7',
  ropaSombra: '#1E6FA3',
  principal: '#F28C28',
  resalte: '#E2701A',
  agua: '#2FA4E7',
  aguaClara: '#BDE6FF',
  contorno: '#3A2A1E',
  claro: '#FFFFFF',
};
