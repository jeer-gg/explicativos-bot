// Piezas 3D para las escenas (React Three Fiber). Claude las usa al construir cada escena.
// Unidades en metros: el suelo está en y = 0 y una persona mide unos 1,6.
import React from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {aparecer, desaparecer, rebote, flotar, mover, momento} from './lib';
import type {EscenaProps, Palabra, Paleta} from './lib';

export {aparecer, desaparecer, rebote, flotar, mover, momento};
export type {EscenaProps, Palabra, Paleta};

export type V3 = [number, number, number];

/** Aspecto global que fija el video: "dibujo" (sombreado de caricatura) o "plastilina". */
export const ASPECTO = {dibujo: true};

let degradado: THREE.DataTexture | null = null;
const tonos = () => {
  if (!degradado) {
    degradado = new THREE.DataTexture(new Uint8Array([120, 120, 120, 255, 200, 200, 200, 255, 255, 255, 255, 255]), 3, 1, THREE.RGBAFormat);
    degradado.minFilter = THREE.NearestFilter;
    degradado.magFilter = THREE.NearestFilter;
    degradado.needsUpdate = true;
  }
  return degradado;
};

/** Material base del canal (en modo dibujo: sombreado de caricatura en 3 tonos). */
export const Mat: React.FC<{color: string; rugosidad?: number; metal?: number; brillo?: string; intensidadBrillo?: number; opacidad?: number}> = ({
  color,
  rugosidad = 0.62,
  metal = 0,
  brillo,
  intensidadBrillo = 1,
  opacidad = 1,
}) =>
  ASPECTO.dibujo && metal < 0.5 ? (
    <meshToonMaterial
      color={color}
      gradientMap={tonos()}
      emissive={brillo ?? '#000000'}
      emissiveIntensity={brillo ? intensidadBrillo : 0}
      transparent={opacidad < 1}
      opacity={opacidad}
    />
  ) : (
  <meshStandardMaterial
    color={color}
    roughness={rugosidad}
    metalness={metal}
    emissive={brillo ?? '#000000'}
    emissiveIntensity={brillo ? intensidadBrillo : 0}
    transparent={opacidad < 1}
    opacity={opacidad}
  />
);

export type Expresion = 'neutral' | 'feliz' | 'sorprendido' | 'triste' | 'enojado' | 'pensando';

/**
 * Muñeco: cuerpo de cápsula, cabeza esférica, brazos y cara expresiva (ojos con brillo, cejas, boca).
 * - mirar: giro de la cabeza en radianes (positivo = hacia su izquierda)
 * - brazoIzq / brazoDer: ángulo de cada brazo (0 = caído, 1.4 = horizontal, 2.6 = arriba)
 * - frame: si se pasa, parpadea solo
 */
export const Muneco: React.FC<{
  color: string;
  posicion?: V3;
  rotacion?: number; // giro del cuerpo en Y
  altura?: number;
  expresion?: Expresion;
  mirar?: number;
  inclinar?: number; // inclinación de la cabeza (lado)
  brazoIzq?: number;
  brazoDer?: number;
  conCara?: boolean;
  colorCara?: string;
  frame?: number;
  escala?: number;
  children?: React.ReactNode; // objetos que lleva (en coordenadas del muñeco)
}> = ({
  color,
  posicion = [0, 0, 0],
  rotacion = 0,
  altura = 1.6,
  expresion = 'neutral',
  mirar = 0,
  inclinar = 0,
  brazoIzq = 0.12,
  brazoDer = 0.12,
  conCara = true,
  colorCara = '#1A1A1F',
  frame,
  escala = 1,
  children,
}) => {
  const s = (altura / 1.6) * escala;
  const parpadeo = frame !== undefined && frame % 105 > 100 ? 0.12 : 1;
  const ceja = {neutral: 0, feliz: 0.12, sorprendido: 0.32, triste: -0.35, enojado: 0.45, pensando: 0.2}[expresion];
  const cejaY = {neutral: 0, feliz: 0.01, sorprendido: 0.04, triste: 0, enojado: -0.015, pensando: 0.02}[expresion];
  const blanco = '#F7F4EE';
  const brazo = (lado: 1 | -1, angulo: number) => (
    <group position={[0.33 * lado, 1.02, 0]} rotation={[0, 0, angulo * lado]}>
      <mesh position={[0, -0.24, 0]} castShadow>
        <capsuleGeometry args={[0.075, 0.36, 6, 12]} />
        <Mat color={color} />
      </mesh>
    </group>
  );
  return (
    <group position={posicion} rotation={[0, rotacion, 0]} scale={s}>
      {/* cuerpo */}
      <mesh position={[0, 0.62, 0]} castShadow receiveShadow>
        <capsuleGeometry args={[0.31, 0.62, 8, 20]} />
        <Mat color={color} />
      </mesh>
      {brazo(1, brazoIzq)}
      {brazo(-1, brazoDer)}
      {/* cabeza */}
      <group position={[0, 1.36, 0]} rotation={[0, mirar, inclinar]}>
        <mesh castShadow>
          <sphereGeometry args={[0.26, 32, 24]} />
          <Mat color={color} />
        </mesh>
        {conCara ? (
          <group position={[0, 0.02, 0.2]}>
            {[-1, 1].map((l) => (
              <group key={l} position={[0.085 * l, 0.03, 0.035]} scale={[1, parpadeo, 1]}>
                <mesh>
                  <sphereGeometry args={[0.052, 16, 12]} />
                  <meshStandardMaterial color={blanco} roughness={0.3} />
                </mesh>
                <mesh position={[0, -0.005, 0.038]}>
                  <sphereGeometry args={[0.027, 12, 10]} />
                  <meshStandardMaterial color={colorCara} roughness={0.2} />
                </mesh>
                <mesh position={[0.01, 0.01, 0.06]}>
                  <sphereGeometry args={[0.008, 8, 6]} />
                  <meshBasicMaterial color="#FFFFFF" />
                </mesh>
                {/* ceja */}
                <mesh position={[0, 0.085 + cejaY, 0.02]} rotation={[0, 0, ceja * -l]}>
                  <boxGeometry args={[0.07, 0.016, 0.02]} />
                  <meshStandardMaterial color={colorCara} />
                </mesh>
              </group>
            ))}
            <Boca expresion={expresion} color={colorCara} />
          </group>
        ) : null}
      </group>
      {children}
    </group>
  );
};

const Boca: React.FC<{expresion: Expresion; color: string}> = ({expresion, color}) => {
  const y = -0.085;
  if (expresion === 'sorprendido')
    return (
      <mesh position={[0, y, 0.05]} scale={[1, 1.3, 0.5]}>
        <sphereGeometry args={[0.03, 12, 10]} />
        <meshStandardMaterial color={color} />
      </mesh>
    );
  if (expresion === 'feliz' || expresion === 'triste')
    return (
      <mesh position={[0, expresion === 'feliz' ? y + 0.01 : y - 0.02, 0.05]} rotation={[0, 0, expresion === 'feliz' ? Math.PI : 0]}>
        <torusGeometry args={[0.045, 0.011, 8, 20, Math.PI]} />
        <meshStandardMaterial color={color} />
      </mesh>
    );
  return (
    <mesh position={[0, y, 0.05]} rotation={[0, 0, expresion === 'pensando' ? 0.25 : 0]}>
      <boxGeometry args={[expresion === 'enojado' ? 0.08 : 0.06, 0.014, 0.02]} />
      <meshStandardMaterial color={color} />
    </mesh>
  );
};

/** Grupo de muñecos sin protagonismo (gente, público, fila). Distribución estable, sin azar real. */
export const Multitud: React.FC<{
  filas: number;
  columnas: number;
  color: string;
  centro?: V3;
  separacion?: number;
  frame?: number;
  conCara?: boolean;
  mirarA?: V3; // si se indica, todas las cabezas miran a ese punto
  huecos?: [number, number][]; // [fila, columna] que quedan vacíos
  aparicion?: number; // 0..1, van apareciendo de atrás hacia delante
}> = ({filas, columnas, color, centro = [0, 0, -3], separacion = 0.95, frame = 0, conCara = false, mirarA, huecos = [], aparicion = 1}) => {
  const items: React.ReactNode[] = [];
  for (let f = 0; f < filas; f++) {
    for (let c = 0; c < columnas; c++) {
      if (huecos.some(([hf, hc]) => hf === f && hc === c)) continue;
      const h = Math.sin(f * 12.9898 + c * 78.233) * 43758.5453;
      const r = h - Math.floor(h);
      const x = centro[0] + (c - (columnas - 1) / 2) * separacion + (r - 0.5) * 0.25;
      const z = centro[2] - f * separacion * 0.9 + (r - 0.5) * 0.2;
      const orden = (filas - f) / filas;
      const vis = Math.min(1, Math.max(0, (aparicion - orden * 0.5) * 2));
      if (vis <= 0) continue;
      const mirar = mirarA ? Math.atan2(mirarA[0] - x, mirarA[2] - z) : (r - 0.5) * 0.4;
      items.push(
        <Muneco
          key={`${f}-${c}`}
          color={color}
          posicion={[x, centro[1] + flotar(frame + f * 7 + c * 13, 0.015, 60), z]}
          altura={1.5 + r * 0.2}
          escala={vis}
          mirar={mirar * 0.8}
          conCara={conCara}
          frame={frame + Math.round(r * 90)}
        />,
      );
    }
  }
  return <group>{items}</group>;
};

/** Caja (puede usarse para muebles, paredes, bloques, edificios). */
export const Bloque: React.FC<{tam: V3; posicion?: V3; rotacion?: V3; color: string; rugosidad?: number; brillo?: string}> = ({
  tam,
  posicion = [0, 0, 0],
  rotacion = [0, 0, 0],
  color,
  rugosidad,
  brillo,
}) => (
  <mesh position={posicion} rotation={rotacion} castShadow receiveShadow>
    <boxGeometry args={tam} />
    <Mat color={color} rugosidad={rugosidad} brillo={brillo} />
  </mesh>
);

/** Barra/cilindro entre dos puntos (cables, palos, flechas, conexiones). progreso 0..1 la va dibujando. */
export const Linea: React.FC<{desde: V3; hasta: V3; grosor?: number; color: string; progreso?: number; brillo?: boolean; discontinua?: boolean}> = ({
  desde,
  hasta,
  grosor = 0.02,
  color,
  progreso = 1,
  brillo = false,
  discontinua = false,
}) => {
  const a = new THREE.Vector3(...desde);
  const b = new THREE.Vector3(...hasta);
  const fin = a.clone().lerp(b, Math.max(0.001, Math.min(1, progreso)));
  const tramos = discontinua ? Math.max(1, Math.round(a.distanceTo(fin) / 0.12)) : 1;
  const piezas: React.ReactNode[] = [];
  for (let i = 0; i < tramos; i++) {
    const p0 = a.clone().lerp(fin, i / tramos);
    const p1 = a.clone().lerp(fin, (i + (discontinua ? 0.55 : 1)) / tramos);
    const largo = p0.distanceTo(p1);
    const medio = p0.clone().add(p1).multiplyScalar(0.5);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), p1.clone().sub(p0).normalize());
    piezas.push(
      <mesh key={i} position={medio} quaternion={q}>
        <cylinderGeometry args={[grosor, grosor, largo, 8]} />
        {brillo ? <meshBasicMaterial color={color} toneMapped={false} /> : <Mat color={color} />}
      </mesh>,
    );
  }
  return <group>{piezas}</group>;
};

/** Aro luminoso en el suelo (para señalar, agrupar o marcar a alguien). */
export const Aro: React.FC<{posicion?: V3; radio?: number; color: string; progreso?: number; grosor?: number}> = ({
  posicion = [0, 0, 0],
  radio = 0.55,
  color,
  progreso = 1,
  grosor = 0.025,
}) => (
  <mesh position={[posicion[0], posicion[1] + 0.01, posicion[2]]} rotation={[-Math.PI / 2, 0, 0]}>
    <torusGeometry args={[radio, grosor, 8, 64, Math.PI * 2 * Math.max(0.001, Math.min(1, progreso))]} />
    <meshBasicMaterial color={color} toneMapped={false} />
  </mesh>
);

/** Esfera brillante (luces, energía, partículas, puntos de datos). Puede iluminar el entorno. */
export const Brillo: React.FC<{posicion: V3; color: string; radio?: number; luz?: number}> = ({posicion, color, radio = 0.06, luz = 0}) => (
  <group position={posicion}>
    <mesh>
      <sphereGeometry args={[radio, 16, 12]} />
      <meshBasicMaterial color={color} toneMapped={false} />
    </mesh>
    {luz > 0 ? <pointLight color={color} intensity={luz} distance={3} decay={2} /> : null}
  </group>
);

/** Cono de luz visible (efecto "reflector" con polvo en el aire). Va de `arriba` al suelo. */
export const ConoDeLuz: React.FC<{posicion?: V3; altura?: number; radio?: number; color: string; opacidad?: number}> = ({
  posicion = [0, 0, 0],
  altura = 6,
  radio = 0.9,
  color,
  opacidad = 0.08,
}) => (
  <mesh position={[posicion[0], posicion[1] + altura / 2, posicion[2]]}>
    <coneGeometry args={[radio, altura, 40, 1, true]} />
    <meshBasicMaterial color={color} transparent opacity={opacidad} depthWrite={false} side={THREE.DoubleSide} toneMapped={false} />
  </mesh>
);

// ---------- Texto dentro del mundo 3D (carteles, bocadillos, pantallas, números) ----------

const texturas = new Map<string, THREE.CanvasTexture>();

const texturaDeTexto = (texto: string, fondo: string, colorTexto: string, cola: boolean, fuente: string, borde = '') => {
  const clave = [texto, fondo, colorTexto, cola, fuente, borde].join('|');
  const hecha = texturas.get(clave);
  if (hecha) return hecha;
  const lienzo = document.createElement('canvas');
  const ctx = lienzo.getContext('2d')!;
  const tamFuente = 120;
  ctx.font = `900 ${tamFuente}px ${fuente}`;
  const lineas = texto.split('\n');
  const ancho = Math.max(...lineas.map((l) => ctx.measureText(l).width)) + 140;
  const alto = lineas.length * tamFuente * 1.15 + 110;
  const extra = cola ? 70 : 0;
  lienzo.width = Math.ceil(ancho);
  lienzo.height = Math.ceil(alto + extra);
  const c = lienzo.getContext('2d')!;
  if (fondo !== 'transparent') {
    c.fillStyle = fondo;
    const r = 60;
    c.beginPath();
    c.moveTo(r, 0);
    c.arcTo(ancho, 0, ancho, alto, r);
    c.arcTo(ancho, alto, 0, alto, r);
    c.arcTo(0, alto, 0, 0, r);
    c.arcTo(0, 0, ancho, 0, r);
    c.closePath();
    c.fill();
    if (cola) {
      c.beginPath();
      c.moveTo(ancho / 2 - 45, alto - 2);
      c.lineTo(ancho / 2 + 45, alto - 2);
      c.lineTo(ancho / 2, alto + extra);
      c.closePath();
      c.fill();
    }
  }
  c.fillStyle = colorTexto;
  c.font = `900 ${tamFuente}px ${fuente}`;
  c.textAlign = 'center';
  c.textBaseline = 'middle';
  lineas.forEach((l, i) => {
    const y = 55 + tamFuente * 0.58 + i * tamFuente * 1.15;
    if (borde) {
      c.strokeStyle = borde;
      c.lineWidth = 22;
      c.lineJoin = 'round';
      c.strokeText(l, ancho / 2, y);
    }
    c.fillText(l, ancho / 2, y);
  });
  const tex = new THREE.CanvasTexture(lienzo);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  texturas.set(clave, tex);
  return tex;
};

export const FUENTE = {familia: 'sans-serif'};

/**
 * Cartel con texto corto dentro del mundo (1 a 3 palabras; usa \n para otra línea).
 * - alto: altura del cartel en metros (el ancho se calcula solo)
 * - cola: añade el piquito de bocadillo de diálogo
 * - mirarCamara: queda siempre de frente (por defecto sí)
 */
export const Cartel: React.FC<{
  texto: string;
  posicion: V3;
  alto?: number;
  fondo?: string;
  colorTexto?: string;
  cola?: boolean;
  escala?: number;
  rotacion?: V3;
  opacidad?: number;
  borde?: string; // contorno del texto (útil con fondo "transparent")
}> = ({texto, posicion, alto = 0.32, fondo = '#F7F4EE', colorTexto = '#16161A', cola = false, escala = 1, rotacion = [0, 0, 0], opacidad = 1, borde = ''}) => {
  const tex = texturaDeTexto(texto, fondo, colorTexto, cola, FUENTE.familia, borde);
  const img = tex.image as HTMLCanvasElement;
  // Siempre de frente a la cámara (salvo que se pida una rotación fija), para que se lea bien.
  const camara = useThree((st) => st.camera);
  const ref = React.useRef<THREE.Mesh>(null);
  const fijo = rotacion.some((r) => r !== 0);
  React.useLayoutEffect(() => {
    const m = ref.current;
    if (!m || fijo || !m.parent) return;
    m.parent.updateWorldMatrix(true, false);
    const padre = new THREE.Quaternion();
    m.parent.getWorldQuaternion(padre);
    m.quaternion.copy(padre.invert().multiply(camara.quaternion));
  });
  const h = alto * (img.height / (img.height - (cola ? 70 : 0)));
  const w = h * (img.width / img.height);
  if (escala <= 0.001) return null;
  return (
    <mesh ref={ref} position={posicion} rotation={fijo ? rotacion : undefined} scale={escala}>
      <planeGeometry args={[w, h]} />
      <meshBasicMaterial map={tex} transparent opacity={opacidad} toneMapped={false} depthWrite={false} />
    </mesh>
  );
};

/** Escena de respaldo: se usa si una escena generada no funciona. */
export const EscenaRespaldo3D: React.FC<EscenaProps> = ({frame, fps, paleta, rotulo}) => {
  const [prota, gente, luz] = paleta.acentos;
  const entra = rebote(frame, fps, 3);
  return (
    <group>
      <Multitud filas={3} columnas={5} color={gente} centro={[0, 0, -2.2]} frame={frame} />
      <Muneco color={prota} posicion={[0, 0, 0]} escala={0.6 + 0.4 * entra} expresion="feliz" frame={frame}
        brazoDer={mover(frame, [10, 22], [0.12, 2.4])} mirar={flotar(frame, 0.25, 80)} />
      <Aro color={luz} radio={0.6} progreso={aparecer(frame, 6, 20)} />
      {rotulo ? <Cartel texto={rotulo} posicion={[0, 2.25, 0.2]} cola escala={rebote(frame, fps, 12)} /> : null}
    </group>
  );
};

// ---------- Piezas con contorno de dibujo, armado y señalización ----------

export type Forma = 'caja' | 'cilindro' | 'esfera' | 'capsula' | 'cono' | 'toro' | 'media_esfera' | 'tubo';

const geometrias = new Map<string, THREE.BufferGeometry>();
const geometria = (forma: Forma, a: number[]) => {
  const clave = forma + a.join(',');
  let g = geometrias.get(clave);
  if (g) return g;
  if (forma === 'caja') g = new THREE.BoxGeometry(a[0] ?? 1, a[1] ?? 1, a[2] ?? 1);
  else if (forma === 'cilindro') g = new THREE.CylinderGeometry(a[0] ?? 0.5, a[1] ?? a[0] ?? 0.5, a[2] ?? 1, a[3] ?? 32);
  else if (forma === 'esfera') g = new THREE.SphereGeometry(a[0] ?? 0.5, 32, 24);
  else if (forma === 'media_esfera') g = new THREE.SphereGeometry(a[0] ?? 0.5, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2);
  else if (forma === 'capsula') g = new THREE.CapsuleGeometry(a[0] ?? 0.2, a[1] ?? 0.6, 8, 16);
  else if (forma === 'cono') g = new THREE.ConeGeometry(a[0] ?? 0.5, a[1] ?? 1, 32);
  else if (forma === 'toro') g = new THREE.TorusGeometry(a[0] ?? 0.5, a[1] ?? 0.1, 12, 48, a[2] ?? Math.PI * 2);
  else g = new THREE.CylinderGeometry(a[0] ?? 0.5, a[0] ?? 0.5, a[1] ?? 1, 32, 1, true); // tubo abierto
  geometrias.set(clave, g);
  return g;
};
const bordes = new Map<THREE.BufferGeometry, THREE.EdgesGeometry>();

/**
 * Pieza con contorno negro fino de dibujo (el look de los explicativos 3D ilustrados).
 * medidas según la forma:
 *  caja [ancho, alto, fondo] · cilindro [radioArriba, radioAbajo, alto] · esfera / media_esfera [radio]
 *  capsula [radio, largo] · cono [radio, alto] · toro [radio, grosor, arco] · tubo [radio, alto]
 */
export const Pieza: React.FC<{
  forma: Forma;
  medidas: number[];
  color: string;
  posicion?: V3;
  rotacion?: V3;
  escala?: number | V3;
  contorno?: boolean;
  brillo?: string;
  opacidad?: number;
  metal?: number;
  children?: React.ReactNode;
}> = ({forma, medidas, color, posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1, contorno = true, brillo, opacidad = 1, metal = 0, children}) => {
  const g = geometria(forma, medidas);
  let e = bordes.get(g);
  if (!e) {
    e = new THREE.EdgesGeometry(g, 35);
    bordes.set(g, e);
  }
  if ((typeof escala === 'number' ? escala : Math.min(...escala)) <= 0.001) return null;
  return (
    <group position={posicion} rotation={rotacion} scale={escala}>
      <mesh geometry={g} castShadow receiveShadow>
        <Mat color={color} brillo={brillo} opacidad={opacidad} metal={metal} />
      </mesh>
      {contorno ? (
        <>
          <mesh geometry={g} scale={1.025}>
            <meshBasicMaterial color="#1B1B1F" side={THREE.BackSide} />
          </mesh>
          <lineSegments geometry={e}>
            <lineBasicMaterial color="#1B1B1F" />
          </lineSegments>
        </>
      ) : null}
      {children}
    </group>
  );
};

/**
 * Animación de armado: la pieza cae desde arriba y rebota al llegar en el fotograma `t`.
 * Devuelve {y, escala, giro}: súmalo a la posición/rotación de la pieza.
 * Antes de `t` la pieza está arriba y fuera de cuadro (escala 0 si `aparece` es true).
 */
export const caer = (frame: number, fps: number, t: number, altura = 2.2, aparece = true) => {
  const f = frame - t;
  if (f < -10) return {y: altura, escala: aparece ? 0 : 1, giro: 0.6};
  const bajada = Math.min(1, Math.max(0, (f + 10) / 10));
  const golpe = f > 0 ? Math.exp(-f / 5) * Math.sin(f / 1.6) * 0.06 : 0;
  return {y: altura * (1 - bajada * bajada) + golpe, escala: aparece ? Math.min(1, (f + 10) / 4) : 1, giro: 0.6 * (1 - bajada)};
};

/** Etiqueta corta que señala una parte: texto con contorno y una línea fina hasta el punto. */
export const Etiqueta: React.FC<{texto: string; punto: V3; desplazamiento?: V3; escala?: number; color?: string; alto?: number}> = ({
  texto,
  punto,
  desplazamiento = [0.5, 0.5, 0],
  escala = 1,
  color = '#FFFFFF',
  alto = 0.17,
}) => {
  if (escala <= 0.001) return null;
  const donde: V3 = [punto[0] + desplazamiento[0], punto[1] + desplazamiento[1], punto[2] + desplazamiento[2]];
  return (
    <group>
      <Linea desde={punto} hasta={[donde[0], donde[1] - alto * 0.55, donde[2]]} grosor={0.006} color="#1B1B1F" progreso={escala} />
      <Cartel texto={texto} posicion={donde} alto={alto} fondo="transparent" colorTexto={color} borde="#1B1B1F" escala={escala} />
    </group>
  );
};

/** Cota de medida entre dos puntos (como en un plano): línea con topes y el texto en medio. */
export const Medida: React.FC<{desde: V3; hasta: V3; texto: string; progreso?: number; color?: string}> = ({desde, hasta, texto, progreso = 1, color = '#1B1B1F'}) => {
  if (progreso <= 0.001) return null;
  const medio: V3 = [(desde[0] + hasta[0]) / 2, (desde[1] + hasta[1]) / 2 + 0.12, (desde[2] + hasta[2]) / 2];
  return (
    <group>
      <Linea desde={desde} hasta={hasta} grosor={0.008} color={color} progreso={progreso} />
      <Pieza forma="esfera" medidas={[0.025]} color={color} posicion={desde} contorno={false} />
      {progreso >= 1 ? <Pieza forma="esfera" medidas={[0.025]} color={color} posicion={hasta} contorno={false} /> : null}
      <Cartel texto={texto} posicion={medio} alto={0.16} fondo="transparent" colorTexto="#FFFFFF" borde="#1B1B1F" escala={Math.min(1, progreso * 1.5)} />
    </group>
  );
};

/** Flecha para fuerzas, flujos o movimiento (de `desde` a `hasta`). */
export const Flecha: React.FC<{desde: V3; hasta: V3; color: string; grosor?: number; progreso?: number}> = ({desde, hasta, color, grosor = 0.03, progreso = 1}) => {
  if (progreso <= 0.001) return null;
  const a = new THREE.Vector3(...desde);
  const b = a.clone().lerp(new THREE.Vector3(...hasta), Math.min(1, progreso));
  const dir = b.clone().sub(a);
  const largo = dir.length();
  const punta = Math.min(grosor * 4, largo * 0.4);
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  const fin = a.clone().add(dir.clone().normalize().multiplyScalar(largo - punta));
  return (
    <group>
      <Linea desde={desde} hasta={[fin.x, fin.y, fin.z]} grosor={grosor} color={color} />
      <mesh position={b.clone().sub(dir.clone().normalize().multiplyScalar(punta / 2))} quaternion={q} castShadow>
        <coneGeometry args={[grosor * 2.2, punta, 16]} />
        <Mat color={color} />
      </mesh>
    </group>
  );
};

/** Ojos simpáticos para darle vida a un objeto (pégalos en su cara frontal). mirar: [-1..1, -1..1]. */
export const Ojos: React.FC<{posicion: V3; tam?: number; separacion?: number; mirar?: [number, number]; frame?: number; rotacion?: V3}> = ({
  posicion,
  tam = 0.07,
  separacion = 0.18,
  mirar = [0, 0],
  frame,
  rotacion = [0, 0, 0],
}) => {
  const parpadeo = frame !== undefined && frame % 95 > 90 ? 0.12 : 1;
  return (
    <group position={posicion} rotation={rotacion}>
      {[-1, 1].map((l) => (
        <group key={l} position={[(separacion / 2) * l, 0, 0]} scale={[1, parpadeo, 1]}>
          <Pieza forma="esfera" medidas={[tam]} color="#FFFFFF" escala={[1, 1.15, 0.45]} />
          <mesh position={[mirar[0] * tam * 0.35, mirar[1] * tam * 0.35 - tam * 0.1, tam * 0.42]}>
            <sphereGeometry args={[tam * 0.45, 16, 12]} />
            <meshBasicMaterial color="#1B1B1F" />
          </mesh>
        </group>
      ))}
    </group>
  );
};
