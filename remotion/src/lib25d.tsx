// Técnica 2.5D: piezas 3D bien formadas (lo que gira, se abre o tiene volumen) y recortes 2D
// dibujados con curvas (lo orgánico: manos, personas, agua, humo, fuego, plantas), todo en el
// mismo mundo, con el mismo contorno, la misma paleta y la misma sombra suave.
//
// <<API2.5D
// import {Recorte, Mano, Persona2D, Agua, Efecto, Planta, Nube, Cabeza2D, Sombra, Habitacion,
//         Inodoro, Grifo, Tuberia, Engranaje, Bombillo, Enchufe, Cajon} from '../lib25d';
//
// 2D (recortes planos dentro del mundo, miran hacia la cámara, +z). Todos llevan frame y fps.
// - <Mano pose="agarra|senala|abierta" posicion={[x,y,z]} ancho={0.9} espejo? rotacion? escala? frame fps />
//     agarra/senala: la mano mira a la IZQUIERDA y la manga sale por la derecha (espejo={true} al revés).
// - <Persona2D pose="parado|camina|senala|piensa|sorprendida" color? alto={1.6} posicion espejo? frame fps />
//     persona sin cara, con los pies en posicion (y = 0 es el suelo). Camina hacia la derecha
//     (espejo para la izquierda); usa "camina" SOLO mientras avanza a 0,6-0,9 unidades por segundo.
// - <Agua ancho alto posicion nivel={0..1} fuga={[u,v]|null} fuerzaFuga? frame fps />
//     cuerpo de agua con superficie que se mueve; fuga = burbujas que se van hacia ese punto.
// - <Efecto tipo="chorro|gotas|burbujas|vapor|fuego|chispa|ondas|destello" posicion tam={0.6} fuerza? color? frame fps />
// - <Planta posicion alto />  <Nube posicion ancho />  <Cabeza2D posicion alto fuerza={0..1 brillo del cerebro} />
// - <Recorte dibujo="nombre" ancho alto posicion opciones={{pose, nivel, fuerza, color}} frame fps /> (genérico)
// - <Sombra posicion={[x,0,z]} radio={1} /> sombra suave en el suelo debajo de cada cosa apoyada.
// - <Habitacion /> pared con luz de ventana y piso de madera (para escenas de interior).
//
// 3D (sombreado de caricatura con contorno, listas y bien formadas):
// - <Inodoro corte={0..1 quita el frente del tanque} tapa={0..1 levanta la tapa} nivel={0..1} fuga={0..1}
//     resaltarTapon? posicion escala frame fps />  (taza + tanque con tapón, flota, válvula, cadena)
// - <Grifo abierto={0..1} gotea? posicion escala frame fps />  (llave con chorro 2D)
// - <Tuberia puntos={[[x,y,z],...]} radio={0.08} color flujo={0..1} colorFlujo? frame fps />
// - <Engranaje dientes={12} radio={0.5} grosor={0.15} giro={radianes} color posicion rotacion />
// - <Bombillo encendido={0..1} posicion escala />
// - <Enchufe posicion rotacion escala />
// - <Cajon abierto={0..1} color ancho alto fondo posicion />
// Regla: lo que gira, se abre o se ve por dentro va en 3D; lo vivo, blando o líquido va en 2D.
// Cada cosa apoyada en el suelo lleva su <Sombra />.
// API2.5D>>
import React, {useMemo} from 'react';
import * as THREE from 'three';
import {COLORES_BASE, Colores, DIBUJOS, NombreDibujo, Opc} from './dibujos2d';
import {ASPECTO, Mat, Pieza, V3} from './lib3d';

/** Lo fija el video según la página: colores del 2D, contorno y colores de la habitación. */
export const ESTILO25D: {colores: Colores; contorno: boolean; pared: string; piso: string; luz: string} = {
  colores: {...COLORES_BASE},
  contorno: true,
  pared: '#F1E4CF',
  piso: '#C89B6D',
  luz: '#FFF6E3',
};

export const oscurecer = (hex: string, k = 0.75) => {
  const n = parseInt(hex.replace('#', ''), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.min(255, Math.round(v * k)));
  return '#' + c.map((v) => v.toString(16).padStart(2, '0')).join('');
};

// ---------- recortes 2D ----------
type Comun = {frame: number; fps: number; posicion?: V3; rotacion?: V3; escala?: number; opacidad?: number};

export const Recorte: React.FC<
  Comun & {dibujo: NombreDibujo; ancho: number; alto: number; opciones?: Partial<Opc>; espejo?: boolean; resolucion?: number}
> = ({dibujo, ancho, alto, opciones, espejo = false, resolucion = 512, frame, fps, posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1, opacidad = 1}) => {
  const lienzo = useMemo(() => {
    const c = document.createElement('canvas');
    const proporcion = alto / ancho;
    c.width = proporcion > 1 ? Math.round(resolucion / proporcion) : resolucion;
    c.height = proporcion > 1 ? resolucion : Math.round(resolucion * proporcion);
    const textura = new THREE.CanvasTexture(c);
    textura.colorSpace = THREE.SRGBColorSpace;
    textura.anisotropy = 4;
    return {c, textura};
  }, [ancho, alto, resolucion]);
  if (escala <= 0.001) return null;
  const x = lienzo.c.getContext('2d');
  if (x) {
    x.clearRect(0, 0, lienzo.c.width, lienzo.c.height);
    const o: Opc = {t: frame / fps, c: {...ESTILO25D.colores, ...(opciones?.c || {})}, contorno: ESTILO25D.contorno, ...opciones} as Opc;
    o.c = {...ESTILO25D.colores, ...(opciones?.c || {})};
    o.contorno = ESTILO25D.contorno;
    DIBUJOS[dibujo](x, lienzo.c.width, lienzo.c.height, o);
    lienzo.textura.needsUpdate = true;
  }
  return (
    <mesh position={posicion} rotation={rotacion} scale={[espejo ? -escala : escala, escala, escala]}>
      <planeGeometry args={[ancho, alto]} />
      <meshBasicMaterial map={lienzo.textura} transparent alphaTest={0.03} toneMapped={false} side={THREE.DoubleSide} opacity={opacidad} />
    </mesh>
  );
};

export const Mano: React.FC<Comun & {pose?: 'agarra' | 'senala' | 'abierta'; ancho?: number; espejo?: boolean}> = ({pose = 'agarra', ancho = 0.9, ...r}) => (
  <Recorte dibujo={pose === 'senala' ? 'mano_senala' : pose === 'abierta' ? 'mano_abierta' : 'mano_agarra'} ancho={ancho} alto={ancho} {...r} />
);

export const Persona2D: React.FC<Comun & {pose?: string; color?: string; alto?: number; espejo?: boolean}> = ({pose = 'parado', color, alto = 1.6, posicion = [0, 0, 0], ...r}) => (
  <Recorte dibujo="persona" ancho={alto / 2} alto={alto} posicion={[posicion[0], posicion[1] + alto / 2, posicion[2]]} opciones={{pose, color}} resolucion={512} {...r} />
);

export const Agua: React.FC<Comun & {ancho: number; alto: number; nivel?: number; fuga?: [number, number] | null; fuerzaFuga?: number}> = ({
  ancho, alto, nivel = 0.75, fuga = null, fuerzaFuga = 1, ...r
}) => <Recorte dibujo="agua" ancho={ancho} alto={alto} opciones={{nivel, fuga, fuerza: fuerzaFuga}} {...r} />;

export const Efecto: React.FC<Comun & {tipo: 'chorro' | 'gotas' | 'burbujas' | 'vapor' | 'fuego' | 'chispa' | 'ondas' | 'destello'; tam?: number; fuerza?: number; color?: string}> = ({
  tipo, tam = 0.6, fuerza = 1, color, ...r
}) => <Recorte dibujo={tipo} ancho={tam} alto={tipo === 'chorro' ? tam * 2 : tam} opciones={{fuerza, color}} resolucion={256} {...r} />;

export const Planta: React.FC<Omit<Comun, 'frame' | 'fps'> & {alto?: number; frame?: number; fps?: number}> = ({alto = 0.8, frame = 0, fps = 30, posicion = [0, 0, 0], ...r}) => (
  <Recorte dibujo="planta" ancho={alto} alto={alto} frame={frame} fps={fps} posicion={[posicion[0], posicion[1] + alto / 2, posicion[2]]} resolucion={256} {...r} />
);

export const Nube: React.FC<Comun & {ancho?: number; color?: string}> = ({ancho = 1.2, color, ...r}) => (
  <Recorte dibujo="nube" ancho={ancho} alto={ancho} opciones={{color}} resolucion={256} {...r} />
);

export const Cabeza2D: React.FC<Comun & {alto?: number; fuerza?: number; color?: string; espejo?: boolean}> = ({alto = 1.2, fuerza = 0, color, ...r}) => (
  <Recorte dibujo="cabeza" ancho={alto} alto={alto} opciones={{fuerza, color}} {...r} />
);

// ---------- sombra suave y habitación ----------
let texSombra: THREE.CanvasTexture | null = null;
const sombraTex = () => {
  if (!texSombra) {
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const x = c.getContext('2d')!;
    const g = x.createRadialGradient(64, 64, 4, 64, 64, 62);
    g.addColorStop(0, 'rgba(40,28,18,0.55)');
    g.addColorStop(1, 'rgba(40,28,18,0)');
    x.fillStyle = g;
    x.fillRect(0, 0, 128, 128);
    texSombra = new THREE.CanvasTexture(c);
  }
  return texSombra;
};

export const Sombra: React.FC<{posicion?: V3; radio?: number; fuerza?: number}> = ({posicion = [0, 0, 0], radio = 1, fuerza = 1}) => (
  <mesh position={[posicion[0], posicion[1] + 0.004, posicion[2]]} rotation={[-Math.PI / 2, 0, 0]}>
    <planeGeometry args={[radio * 2, radio * 1.5]} />
    <meshBasicMaterial map={sombraTex()} transparent depthWrite={false} opacity={fuerza} toneMapped={false} />
  </mesh>
);

const texturas = new Map<string, THREE.CanvasTexture>();
const texturaDe = (clave: string, w: number, h: number, dibujar: (x: CanvasRenderingContext2D) => void) => {
  let t = texturas.get(clave);
  if (!t) {
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    dibujar(c.getContext('2d')!);
    t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    texturas.set(clave, t);
  }
  return t;
};

export const Habitacion: React.FC<{ancho?: number; alto?: number; fondo?: number; ventana?: boolean}> = ({ancho = 10, alto = 6, fondo = 3, ventana = true}) => {
  const {pared, piso, luz} = ESTILO25D;
  const contorno = ESTILO25D.colores.contorno;
  const tPared = texturaDe(`pared${pared}${luz}${ventana}`, 512, 320, (x) => {
    x.fillStyle = pared;
    x.fillRect(0, 0, 512, 320);
    if (ventana) {
      x.fillStyle = luz;
      x.beginPath();
      x.moveTo(90, 20);
      x.lineTo(210, 20);
      x.lineTo(250, 250);
      x.lineTo(60, 250);
      x.closePath();
      x.fill();
    }
    x.fillStyle = oscurecer(pared, 0.9);
    x.fillRect(0, 290, 512, 30);
    x.strokeStyle = contorno;
    x.lineWidth = 3;
    x.beginPath();
    x.moveTo(0, 290);
    x.lineTo(512, 290);
    x.stroke();
  });
  const tPiso = texturaDe(`piso${piso}`, 512, 256, (x) => {
    x.fillStyle = piso;
    x.fillRect(0, 0, 512, 256);
    x.strokeStyle = oscurecer(piso, 0.85);
    x.lineWidth = 4;
    for (let i = 0; i < 6; i++) {
      const y = i * 44;
      x.beginPath();
      x.moveTo(0, y);
      x.lineTo(512, y);
      x.stroke();
      for (let k = 0; k < 4; k++) {
        const px = ((k * 150 + i * 70) % 512);
        x.beginPath();
        x.moveTo(px, y);
        x.lineTo(px, y + 44);
        x.stroke();
      }
    }
  });
  return (
    <group>
      <mesh position={[0, alto / 2, -fondo]}>
        <planeGeometry args={[ancho, alto]} />
        <meshBasicMaterial map={tPared} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.002, -fondo / 2 + 1]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[ancho, fondo + 2]} />
        <meshBasicMaterial map={tPiso} toneMapped={false} />
      </mesh>
    </group>
  );
};

// ---------- pieza 3D con geometría propia (mismo contorno que Pieza) ----------
const bordesGeo = new WeakMap<THREE.BufferGeometry, THREE.EdgesGeometry>();
export const PiezaGeo: React.FC<{
  geometria: THREE.BufferGeometry;
  color: string;
  posicion?: V3;
  rotacion?: V3;
  escala?: number | V3;
  contorno?: boolean;
  brillo?: string;
  opacidad?: number;
  metal?: number;
  grosorContorno?: number;
}> = ({geometria, color, posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1, contorno = true, brillo, opacidad = 1, metal = 0, grosorContorno = 1.03}) => {
  let e = bordesGeo.get(geometria);
  if (!e) {
    e = new THREE.EdgesGeometry(geometria, 40);
    bordesGeo.set(geometria, e);
  }
  if ((typeof escala === 'number' ? escala : Math.min(...escala)) <= 0.001) return null;
  return (
    <group position={posicion} rotation={rotacion} scale={escala}>
      <mesh geometry={geometria} castShadow receiveShadow>
        <Mat color={color} brillo={brillo} opacidad={opacidad} metal={metal} />
      </mesh>
      {contorno && ASPECTO.contorno && opacidad >= 1 ? (
        <>
          <mesh geometry={geometria} scale={grosorContorno}>
            <meshBasicMaterial color={ASPECTO.colorContorno} side={THREE.BackSide} />
          </mesh>
          <lineSegments geometry={e}>
            <lineBasicMaterial color={ASPECTO.colorContorno} />
          </lineSegments>
        </>
      ) : null}
    </group>
  );
};

const geos = new Map<string, THREE.BufferGeometry>();
const geo = (clave: string, crear: () => THREE.BufferGeometry) => {
  let g = geos.get(clave);
  if (!g) {
    g = crear();
    geos.set(clave, g);
  }
  return g;
};
const torno = (puntos: [number, number][], seg = 40) => new THREE.LatheGeometry(puntos.map(([r, y]) => new THREE.Vector2(r, y)), seg);

// ---------- inodoro ----------
const BLANCO = '#F6F2EA';
export const Inodoro: React.FC<Comun & {corte?: number; tapa?: number; nivel?: number; fuga?: number; resaltarTapon?: boolean}> = ({
  frame, fps, corte = 0, tapa = 0, nivel = 0.78, fuga = 0, resaltarTapon = false, posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1,
}) => {
  const gTaza = geo('taza', () => torno([[0.001, 0], [0.42, 0], [0.42, 0.33], [0.6, 0.52], [0.84, 0.86], [0.92, 1.0], [0.62, 1.04], [0.5, 0.86], [0.001, 0.86]]));
  const gAro = geo('aro', () => new THREE.TorusGeometry(0.76, 0.075, 14, 48));
  const t = frame / fps;
  const baja = nivel;
  const pulso = resaltarTapon ? 1 + 0.07 * Math.sin(t * 9) : 1;
  const interior = corte > 0.03;
  const yTanque = 1.47; // base del tanque
  const lev = Math.max(0, Math.min(1, tapa));
  return (
    <group position={posicion} rotation={rotacion} scale={escala}>
      <Sombra posicion={[0, 0, 0.35]} radio={1.25} />
      {/* taza */}
      <PiezaGeo geometria={gTaza} color={BLANCO} posicion={[0, 0, 0.78]} escala={[1, 1, 1.22]} />
      <PiezaGeo geometria={gAro} color={BLANCO} posicion={[0, 1.07, 0.78]} rotacion={[Math.PI / 2, 0, 0]} escala={[1, 1.22, 1]} />
      <mesh position={[0, 0.9, 0.78]} rotation={[-Math.PI / 2, 0, 0]} scale={[1, 1.22, 1]}>
        <circleGeometry args={[0.5, 40]} />
        <meshBasicMaterial color={ESTILO25D.colores.agua} toneMapped={false} />
      </mesh>
      {fuga > 0 ? <Efecto tipo="ondas" posicion={[0, 0.92, 0.78]} rotacion={[-Math.PI / 2, 0, 0]} tam={0.7} frame={frame} fps={fps} opacidad={fuga} /> : null}
      {/* cuello y tanque */}
      <Pieza forma="caja" medidas={[1.3, 0.44, 0.5]} color={BLANCO} posicion={[0, 1.25, -0.15]} />
      <group position={[0, yTanque, 0]}>
        <Pieza forma="caja" medidas={[1.7, 1.3, 0.06]} color={BLANCO} posicion={[0, 0.65, -0.42]} />
        <Pieza forma="caja" medidas={[0.06, 1.3, 0.55]} color={BLANCO} posicion={[-0.82, 0.65, -0.15]} />
        <Pieza forma="caja" medidas={[0.06, 1.3, 0.55]} color={BLANCO} posicion={[0.82, 0.65, -0.15]} />
        <Pieza forma="caja" medidas={[1.7, 0.08, 0.55]} color={BLANCO} posicion={[0, 0.02, -0.15]} />
        {corte < 0.995 ? (
          <group position={[0, 0, 0.12]} scale={[1, Math.max(0.001, 1 - corte), 1]}>
            <Pieza forma="caja" medidas={[1.7, 1.3, 0.06]} color={BLANCO} posicion={[0, 0.65, 0]} />
          </group>
        ) : null}
        {/* tapa: se levanta y se va hacia atrás */}
        <Pieza forma="caja" medidas={[1.86, 0.11, 0.7]} color={BLANCO} posicion={[0.9 * lev, 1.36 + 0.9 * lev, -0.15 - 0.3 * lev]} rotacion={[0, 0, -0.35 * lev]} escala={lev > 0.98 ? 0.001 : 1} />
        {interior ? (
          <group>
            <Agua ancho={1.58} alto={1.18} posicion={[0, 0.65, -0.33]} nivel={baja} fuga={fuga > 0 ? [0.39, 0.1] : null} fuerzaFuga={fuga} frame={frame} fps={fps} />
            <Pieza forma="cilindro" medidas={[0.07, 0.07, 0.95]} color="#E9E1D3" posicion={[-0.38, 0.55, -0.25]} />
            <Pieza forma="cilindro" medidas={[0.21, 0.24, 0.07]} color="#B9C2CC" posicion={[-0.15, 0.08, -0.12]} />
            <group position={[-0.38, 0.14, -0.12]} rotation={[0, 0, 0.13 * fuga]}>
              <Pieza forma="cilindro" medidas={[0.25, 0.25, 0.06]} color={ESTILO25D.colores.principal} posicion={[0.23, 0, 0]} escala={[pulso, 1, pulso]}
                brillo={resaltarTapon ? ESTILO25D.colores.principal : undefined} />
            </group>
            <Pieza forma="cilindro" medidas={[0.013, 0.013, 0.86]} color="#8A8F96" posicion={[-0.12, 0.57, -0.08]} />
            <Pieza forma="caja" medidas={[0.62, 0.05, 0.05]} color="#8A8F96" posicion={[-0.4, 1.01, -0.05]} />
            <Pieza forma="cilindro" medidas={[0.08, 0.08, 0.8]} color="#B9C2CC" posicion={[0.55, 0.43, -0.15]} />
            <group position={[0.55, 0.83, -0.08]} rotation={[0, 0, 0.45 * Math.max(0, 0.78 - baja) / 0.2]}>
              <Pieza forma="caja" medidas={[0.3, 0.035, 0.035]} color="#8A8F96" posicion={[-0.15, 0, 0]} />
              <Pieza forma="esfera" medidas={[0.13]} color="#E9E1D3" posicion={[-0.32, 0, 0]} />
            </group>
          </group>
        ) : null}
      </group>
    </group>
  );
};

// ---------- grifo ----------
export const Grifo: React.FC<Comun & {abierto?: number; gotea?: boolean; color?: string}> = ({
  frame, fps, abierto = 0, gotea = false, color = '#C9CED6', posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1,
}) => {
  const gCaño = geo('caño', () => {
    const curva = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0.35, 0), new THREE.Vector3(0.05, 0.5, 0), new THREE.Vector3(0.3, 0.5, 0), new THREE.Vector3(0.45, 0.38, 0)]);
    return new THREE.TubeGeometry(curva, 48, 0.055, 16, false);
  });
  return (
    <group position={posicion} rotation={rotacion} scale={escala}>
      <Pieza forma="cilindro" medidas={[0.16, 0.18, 0.08]} color={color} metal={0} posicion={[0, 0.04, 0]} />
      <Pieza forma="cilindro" medidas={[0.07, 0.08, 0.1]} color={color} posicion={[0, 0.12, 0]} />
      <PiezaGeo geometria={gCaño} color={color} posicion={[0, 0.1, 0]} />
      <group position={[0, 0.66, 0]} rotation={[0, 0, -0.9 * abierto]}>
        <Pieza forma="cilindro" medidas={[0.06, 0.06, 0.08]} color={color} />
        <Pieza forma="capsula" medidas={[0.03, 0.26]} color={color} posicion={[-0.17, 0.04, 0]} rotacion={[0, 0, Math.PI / 2 - 0.25]} />
      </group>
      {abierto > 0.02 ? (
        <Efecto tipo="chorro" posicion={[0.45, 0.48 - 0.45 * 0.9, 0]} tam={0.45 * (0.6 + 0.4 * abierto)} fuerza={abierto} frame={frame} fps={fps} />
      ) : gotea ? (
        <Efecto tipo="gotas" posicion={[0.45, 0.28, 0]} tam={0.4} frame={frame} fps={fps} />
      ) : null}
    </group>
  );
};

// ---------- tubería ----------
export const Tuberia: React.FC<Comun & {puntos: V3[]; radio?: number; color?: string; flujo?: number; colorFlujo?: string}> = ({
  puntos, radio = 0.08, color = '#B9C2CC', flujo = 0, colorFlujo, frame, fps, posicion = [0, 0, 0],
}) => {
  const clave = JSON.stringify([puntos, radio]);
  const {g, curva} = useMemo(() => {
    const c = new THREE.CatmullRomCurve3(puntos.map((p) => new THREE.Vector3(...p)), false, 'catmullrom', 0.1);
    return {g: new THREE.TubeGeometry(c, Math.max(24, puntos.length * 24), radio, 18, false), curva: c};
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave]);
  const t = frame / fps;
  const n = 10;
  return (
    <group position={posicion}>
      <PiezaGeo geometria={g} color={color} opacidad={flujo > 0 ? 0.55 : 1} />
      {flujo > 0
        ? Array.from({length: n}, (_, i) => {
            const p = curva.getPointAt((i / n + t * 0.35 * flujo) % 1);
            return <Pieza key={i} forma="esfera" medidas={[radio * 0.55]} color={colorFlujo || ESTILO25D.colores.agua} posicion={[p.x, p.y, p.z]} contorno={false} />;
          })
        : null}
    </group>
  );
};

// ---------- engranaje ----------
export const Engranaje: React.FC<{dientes?: number; radio?: number; grosor?: number; giro?: number; color: string; posicion?: V3; rotacion?: V3; escala?: number}> = ({
  dientes = 12, radio = 0.5, grosor = 0.15, giro = 0, color, posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1,
}) => {
  const g = geo(`eng${dientes}_${radio}_${grosor}`, () => {
    const s = new THREE.Shape();
    const ri = radio * 0.8, paso = (Math.PI * 2) / dientes;
    for (let i = 0; i < dientes; i++) {
      const a = i * paso;
      const pts: [number, number][] = [[ri, a], [radio, a + paso * 0.15], [radio, a + paso * 0.45], [ri, a + paso * 0.6], [ri, a + paso]];
      pts.forEach(([r, ang], k) => {
        const px = Math.cos(ang) * r, py = Math.sin(ang) * r;
        if (i === 0 && k === 0) s.moveTo(px, py);
        else s.lineTo(px, py);
      });
    }
    const hueco = new THREE.Path();
    hueco.absarc(0, 0, radio * 0.22, 0, Math.PI * 2, true);
    s.holes.push(hueco);
    const e = new THREE.ExtrudeGeometry(s, {depth: grosor, bevelEnabled: true, bevelSize: radio * 0.02, bevelThickness: radio * 0.02, bevelSegments: 2});
    e.translate(0, 0, -grosor / 2);
    return e;
  });
  return (
    <group position={posicion} rotation={rotacion} scale={escala}>
      <group rotation={[0, 0, giro]}>
        <PiezaGeo geometria={g} color={color} />
      </group>
    </group>
  );
};

// ---------- bombillo ----------
export const Bombillo: React.FC<{encendido?: number; posicion?: V3; rotacion?: V3; escala?: number}> = ({encendido = 0, posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1}) => {
  const gVidrio = geo('vidrio', () => torno([[0.12, 0], [0.13, 0.12], [0.3, 0.35], [0.34, 0.5], [0.3, 0.66], [0.17, 0.76], [0.001, 0.79]], 40));
  const luz = '#FFE066';
  return (
    <group position={posicion} rotation={rotacion} scale={escala}>
      <PiezaGeo geometria={gVidrio} color={encendido > 0.05 ? '#FFF6C9' : '#EAF4F8'} opacidad={encendido > 0.05 ? 1 : 0.75}
        brillo={encendido > 0.05 ? luz : undefined} posicion={[0, 0.02, 0]} />
      <Pieza forma="cilindro" medidas={[0.125, 0.12, 0.2]} color="#B9C2CC" posicion={[0, -0.08, 0]} />
      {[0, 1, 2].map((i) => (
        <Pieza key={i} forma="toro" medidas={[0.125, 0.018]} color="#9AA3AD" posicion={[0, -0.14 + i * 0.06, 0]} rotacion={[Math.PI / 2, 0, 0]} contorno={false} />
      ))}
      <Pieza forma="cilindro" medidas={[0.05, 0.04, 0.05]} color="#3A3A44" posicion={[0, -0.2, 0]} />
      {encendido > 0.05 ? <Efecto tipo="destello" posicion={[0.36, 0.7, 0.1]} tam={0.35} frame={Math.round(encendido * 30)} fps={30} /> : null}
      {encendido > 0.05 ? <pointLight position={[0, 0.45, 0]} color={luz} intensity={2.5 * encendido} distance={3} /> : null}
    </group>
  );
};

// ---------- enchufe ----------
export const Enchufe: React.FC<{posicion?: V3; rotacion?: V3; escala?: number; color?: string}> = ({posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1, color = '#F6F2EA'}) => (
  <group position={posicion} rotation={rotacion} scale={escala}>
    <Pieza forma="caja" medidas={[0.42, 0.62, 0.05]} color={color} />
    <Pieza forma="caja" medidas={[0.3, 0.44, 0.03]} color={oscurecer(color, 0.95)} posicion={[0, 0, 0.035]} />
    <Pieza forma="caja" medidas={[0.04, 0.12, 0.02]} color="#2B241D" posicion={[-0.07, 0.06, 0.055]} contorno={false} />
    <Pieza forma="caja" medidas={[0.04, 0.12, 0.02]} color="#2B241D" posicion={[0.07, 0.06, 0.055]} contorno={false} />
    <Pieza forma="cilindro" medidas={[0.03, 0.03, 0.02]} color="#2B241D" posicion={[0, -0.1, 0.055]} rotacion={[Math.PI / 2, 0, 0]} contorno={false} />
  </group>
);

// ---------- cajón ----------
export const Cajon: React.FC<{abierto?: number; color?: string; ancho?: number; alto?: number; fondo?: number; posicion?: V3; rotacion?: V3; escala?: number}> = ({
  abierto = 0, color = '#C89B6D', ancho = 1, alto = 0.45, fondo = 0.8, posicion = [0, 0, 0], rotacion = [0, 0, 0], escala = 1,
}) => {
  const e = 0.04;
  const z = abierto * fondo * 0.75;
  const interior = oscurecer(color, 0.8);
  return (
    <group position={posicion} rotation={rotacion} scale={escala}>
      <Pieza forma="caja" medidas={[ancho, e, fondo]} color={color} posicion={[0, alto, 0]} />
      <Pieza forma="caja" medidas={[ancho, e, fondo]} color={color} posicion={[0, 0, 0]} />
      <Pieza forma="caja" medidas={[e, alto, fondo]} color={color} posicion={[-ancho / 2, alto / 2, 0]} />
      <Pieza forma="caja" medidas={[e, alto, fondo]} color={color} posicion={[ancho / 2, alto / 2, 0]} />
      <Pieza forma="caja" medidas={[ancho, alto, e]} color={color} posicion={[0, alto / 2, -fondo / 2]} />
      <group position={[0, 0, z]}>
        <Pieza forma="caja" medidas={[ancho - 0.12, e, fondo - 0.1]} color={interior} posicion={[0, 0.06, 0]} />
        <Pieza forma="caja" medidas={[e, alto * 0.7, fondo - 0.1]} color={interior} posicion={[-(ancho - 0.12) / 2, alto * 0.4, 0]} />
        <Pieza forma="caja" medidas={[e, alto * 0.7, fondo - 0.1]} color={interior} posicion={[(ancho - 0.12) / 2, alto * 0.4, 0]} />
        <Pieza forma="caja" medidas={[ancho - 0.04, alto - 0.06, e]} color={color} posicion={[0, alto / 2, fondo / 2]} />
        <Pieza forma="esfera" medidas={[0.045]} color="#8A8F96" posicion={[0, alto / 2, fondo / 2 + 0.05]} />
      </group>
    </group>
  );
};
