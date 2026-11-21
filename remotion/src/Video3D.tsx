// Video 3D: un solo mundo con un "escenario" por escena, iluminado por su reflector.
// La cámara viaja de un escenario al siguiente sin cortes (un plano continuo), siempre cerca.
import React from 'react';
import {AbsoluteFill, Audio, Easing, Sequence, continueRender, delayRender, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {useThree} from '@react-three/fiber';
import * as THREE from 'three';
import {ANCHO, ALTO} from './lib';
import {ASPECTO, EscenaRespaldo3D, FUENTE, V3} from './lib3d';
import {DURACION_PORTADA, Portada, TarjetaDatos} from './Tarjetas';
import {ESCENAS} from './escenas';
import {Subtitulos} from './Subtitulos';
import {fuente} from './fuente';
import type {PlanVideo} from './Video';

const SEPARACION = 11; // metros entre escenarios
export const estacion = (i: number): V3 => [i * SEPARACION, 0, i % 2 === 0 ? 0 : -1.5];

// Encuadres (desde dónde mira la cámara respecto al centro del escenario).
const ENCUADRES: Record<string, {ojo: V3; mira: V3}> = {
  picado: {ojo: [2.6, 3.4, 4.6], mira: [0, 0.7, 0]},
  frente: {ojo: [0, 1.5, 5.6], mira: [0, 1.0, 0]},
  picado_izq: {ojo: [-2.8, 3.2, 4.4], mira: [0, 0.7, 0]},
  cerca: {ojo: [1.2, 2.0, 3.4], mira: [0, 0.8, 0]},
};
const encuadre = (nombre?: string) => ENCUADRES[nombre ?? 'picado'] ?? ENCUADRES.picado;

const SUAVE = Easing.bezier(0.65, 0, 0.35, 1);
const mezclar = (a: V3, b: V3, p: number): V3 => [a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p, a[2] + (b[2] - a[2]) * p];
const sumar = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const girarY = (v: V3, ang: number): V3 => [v[0] * Math.cos(ang) + v[2] * Math.sin(ang), v[1], -v[0] * Math.sin(ang) + v[2] * Math.cos(ang)];
const escalar = (v: V3, k: number): V3 => [v[0] * k, v[1] * k, v[2] * k];

const calcularCamara = (frame: number, fps: number, plan: PlanVideo) => {
  const T = Math.round(0.6 * fps);
  const inicios = plan.escenas.map((e) => Math.round(e.inicio * fps));
  let actual = 0;
  for (let i = 0; i < inicios.length; i++) if (frame >= inicios[i] - Math.round(T * 0.45)) actual = i;
  const llegada = inicios[actual] - Math.round(T * 0.45);
  const p = actual === 0 ? 1 : interpolate(frame, [llegada, llegada + T], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: SUAVE});
  const local = Math.max(0, frame - inicios[actual]);
  const dur = Math.max(1, Math.round(plan.escenas[actual].duracion * fps));
  const avance = Math.min(1, local / dur);
  // Dentro de la escena: gira despacio alrededor del objeto y se acerca; empujón en la palabra clave.
  let cerca = 1 - 0.14 * avance;
  const clave = plan.escenas[actual].clave;
  if (clave != null) {
    const f = local - Math.round(clave * fps);
    if (f >= 0 && f <= 16) cerca -= Math.sin((f / 16) * Math.PI) * 0.1;
  }
  // Arranque con golpe: el video empieza muy cerca y se abre de golpe en el primer medio segundo.
  if (actual === 0) cerca *= interpolate(local, [0, 14], [0.62, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const giro = (avance - 0.5) * 0.3;
  const previo = encuadre(plan.escenas[Math.max(0, actual - 1)].camara);
  const este = encuadre(plan.escenas[actual].camara);
  const desde = estacion(Math.max(0, actual - 1));
  const hasta = estacion(actual);
  const base = mezclar(desde, hasta, p);
  const viaje = Math.sin(Math.PI * p) * (actual === 0 ? 0 : 1);
  const offOjo = mezclar(previo.ojo, escalar(girarY(este.ojo, giro), cerca), p);
  const offMira = mezclar(previo.mira, este.mira, p);
  const ojo = sumar(base, sumar(offOjo, [0, viaje * 0.8, viaje * 1.2]));
  const mira = sumar(base, offMira);
  return {ojo, mira, actual, inicios};
};

const Camara: React.FC<{ojo: V3; mira: V3}> = ({ojo, mira}) => {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  camera.position.set(...ojo);
  camera.lookAt(...mira);
  camera.updateProjectionMatrix();
  return null;
};

const Reflector: React.FC<{donde: V3; color: string; sombras: boolean}> = ({donde, color, sombras}) => {
  const objetivo = React.useMemo(() => new THREE.Object3D(), []);
  return (
    <>
      <primitive object={objetivo} position={[donde[0], 0.6, donde[2]]} />
      <spotLight
        position={[donde[0] + 0.6, 7.5, donde[2] + 2.2]}
        target={objetivo}
        color={color}
        angle={0.32}
        penumbra={0.75}
        intensity={5.5}
        decay={0}
        castShadow={sombras}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-bias={-0.0004}
      />
    </>
  );
};

/** Textura del suelo: manchas suaves del mismo color (pasto, madera, cemento). */
const texturasSuelo = new Map<string, THREE.CanvasTexture>();
const texturaSuelo = (color: string) => {
  const hecha = texturasSuelo.get(color);
  if (hecha) return hecha;
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const ctx = c.getContext('2d')!;
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 256, 256);
  const base = new THREE.Color(color);
  let semilla = 7;
  const azar = () => ((semilla = (semilla * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 1400; i++) {
    const k = (azar() - 0.5) * 0.22;
    ctx.fillStyle = base.clone().offsetHSL(0, 0, k).getStyle();
    ctx.fillRect(azar() * 256, azar() * 256, 1 + azar() * 3, 2 + azar() * 7);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(60, 20);
  tex.colorSpace = THREE.SRGBColorSpace;
  texturasSuelo.set(color, tex);
  return tex;
};

const Sol: React.FC<{donde: V3}> = ({donde}) => {
  const objetivo = React.useMemo(() => new THREE.Object3D(), []);
  return (
    <>
      <primitive object={objetivo} position={donde} />
      <directionalLight
        position={[donde[0] + 4, 9, donde[2] + 5]}
        target={objetivo}
        intensity={2.3}
        color="#FFF6E5"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-6}
        shadow-camera-right={6}
        shadow-camera-top={6}
        shadow-camera-bottom={-6}
        shadow-camera-near={1}
        shadow-camera-far={30}
        shadow-bias={-0.0005}
      />
    </>
  );
};

// ---------- Diseño de sonido: variado, corto y por debajo de la voz ----------
const WHOOSH = ['whoosh1', 'whoosh3', 'whoosh2', 'whoosh4'];
const GOLPES = ['pop1', 'toc1', 'pop3', 'clic', 'toc2', 'pop2'];

const Efecto: React.FC<{nombre: string; en: number; vol: number; dur?: number}> = ({nombre, en, vol, dur = 1.4}) => {
  const {fps} = useVideoConfig();
  return (
    <Sequence from={Math.max(0, Math.round(en * fps))} durationInFrames={Math.round(dur * fps)}>
      <Audio src={staticFile(`sfx/${nombre}.mp3`)} volume={vol} />
    </Sequence>
  );
};

const Sonidos: React.FC<{plan: PlanVideo}> = ({plan}) => {
  const n = plan.escenas.length;
  const ultima = plan.escenas[n - 1];
  const efectos: React.ReactNode[] = [];
  efectos.push(<Efecto key="impacto" nombre="impacto" en={0} vol={0.42} />);
  if (plan.portada) efectos.push(<Efecto key="swish" nombre="swish" en={DURACION_PORTADA - 0.2} vol={0.14} />);
  plan.escenas.forEach((e, i) => {
    // Transición: se alternan cuatro barridos distintos y uno de cada tres pasos va en silencio.
    if (i > 0 && i % 3 !== 2) efectos.push(<Efecto key={`w${i}`} nombre={WHOOSH[i % WHOOSH.length]} en={e.inicio - 0.3} vol={0.16} />);
    if (e.grafico) {
      efectos.push(<Efecto key={`d${i}`} nombre={i % 2 ? 'ding2' : 'ding1'} en={e.inicio + 0.2} vol={0.2} />);
    } else if (e.clave != null && i > 0) {
      efectos.push(<Efecto key={`g${i}`} nombre={GOLPES[(i * 5) % GOLPES.length]} en={e.inicio + e.clave} vol={0.13} />);
    }
  });
  // Subida de tensión justo antes de la revelación final
  if (n > 3) efectos.push(<Efecto key="riser" nombre="riser" en={ultima.inicio - 1.25} vol={0.12} dur={1.4} />);
  return <>{efectos}</>;
};

const Rotulo: React.FC<{plan: PlanVideo}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const e = plan.escenas.find((x) => x.rotulo && t >= x.inicio + 0.25 && t < x.inicio + x.duracion - 0.12);
  if (!e) return null;
  const pop = spring({frame: frame - Math.round((e.inicio + 0.25) * fps), fps, config: {damping: 13, stiffness: 200}});
  const luz = plan.paleta.acentos[2] ?? '#FFC27A';
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: 1300, display: 'flex', justifyContent: 'center'}}>
      <div
        style={{
          transform: `scale(${0.8 + 0.2 * pop})`,
          opacity: Math.min(1, pop * 1.5),
          background: 'rgba(14,14,18,0.74)',
          border: '2px solid rgba(255,255,255,0.14)',
          borderRadius: 30,
          padding: '14px 46px 22px',
          textAlign: 'center',
          boxShadow: '0 20px 60px rgba(0,0,0,0.45)',
        }}
      >
        <div style={{width: 70, height: 8, borderRadius: 4, background: luz, margin: '0 auto 10px'}} />
        <div style={{fontSize: 96, fontWeight: 900, color: plan.paleta.tinta, letterSpacing: -1, lineHeight: 1.05}}>{e.rotulo}</div>
      </div>
    </div>
  );
};

export const Video3D: React.FC<PlanVideo> = (plan) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const [listo, setListo] = React.useState(false);
  const [espera] = React.useState(() => delayRender('Cargando la fuente'));
  React.useEffect(() => {
    fuente.waitUntilDone().then(() => {
      FUENTE.familia = fuente.fontFamily;
      setListo(true);
      continueRender(espera);
    });
  }, [espera]);

  const cam = calcularCamara(frame, fps, plan);
  const visibles = [cam.actual - 1, cam.actual, cam.actual + 1].filter((i) => i >= 0 && i < plan.escenas.length);
  const cielo = new THREE.Color(plan.paleta.fondo);
  const dia = cielo.getHSL({h: 0, s: 0, l: 0}).l > 0.45;
  ASPECTO.dibujo = dia;
  const [, , luz] = plan.paleta.acentos;
  const colorSuelo = plan.paleta.acentos[4] ?? cielo.clone().lerp(new THREE.Color('#ffffff'), 0.07).getStyle();
  const horizonte = cielo.clone().lerp(new THREE.Color('#ffffff'), 0.55).getStyle();

  return (
    <AbsoluteFill
      style={{
        background: dia ? `linear-gradient(180deg, ${plan.paleta.fondo} 0%, ${horizonte} 70%)` : plan.paleta.fondo,
        fontFamily: fuente.fontFamily,
      }}
    >
      {listo ? (
        <ThreeCanvas width={ANCHO} height={ALTO} shadows gl={{alpha: true, antialias: true}} camera={{fov: 40, near: 0.1, far: 140, position: cam.ojo}}>
          <Camara ojo={cam.ojo} mira={cam.mira} />
          {dia ? null : <color attach="background" args={[plan.paleta.fondo]} />}
          <fog attach="fog" args={dia ? [horizonte, 16, 46] : [plan.paleta.fondo, 10, 28]} />
          {dia ? (
            <>
              <ambientLight intensity={0.35} />
              <hemisphereLight args={['#FFFFFF', colorSuelo, 1.1]} />
              <Sol donde={estacion(cam.actual)} />
            </>
          ) : (
            <>
              <ambientLight intensity={0.32} />
              <hemisphereLight args={['#ffffff', plan.paleta.fondo, 0.35]} />
              <directionalLight position={[cam.mira[0] - 4, 5, cam.mira[2] - 6]} intensity={0.6} color="#cfd8ff" />
              {visibles.map((i) => (
                <Reflector key={`r${i}`} donde={estacion(i)} color={luz} sombras={i === cam.actual} />
              ))}
            </>
          )}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[plan.escenas.length * SEPARACION * 0.5, 0, 0]} receiveShadow>
            <planeGeometry args={[plan.escenas.length * SEPARACION + 80, 80]} />
            <meshStandardMaterial color="#FFFFFF" map={texturaSuelo(colorSuelo)} roughness={0.95} />
          </mesh>
          {visibles.map((i) => {
            const e = plan.escenas[i];
            const Escena = ESCENAS[e.componente] ?? EscenaRespaldo3D;
            return (
              <group key={i} position={estacion(i)}>
                <Escena
                  frame={Math.max(0, frame - cam.inicios[i])}
                  fps={fps}
                  duracion={Math.round(e.duracion * fps)}
                  palabras={e.palabras}
                  paleta={plan.paleta}
                  rotulo={e.rotulo}
                />
              </group>
            );
          })}
        </ThreeCanvas>
      ) : null}

      {dia ? (
        <>
          <TarjetaDatos plan={plan} />
          <Portada plan={plan} />
          {plan.subtitulos ? <Subtitulos plan={plan} titular desde={plan.portada ? DURACION_PORTADA : 0} /> : null}
        </>
      ) : (
        <>
          <AbsoluteFill style={{background: 'radial-gradient(ellipse 75% 62% at 50% 46%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)'}} />
          <Rotulo plan={plan} />
          <TarjetaDatos plan={plan} />
          <Portada plan={plan} />
          {plan.subtitulos ? <Subtitulos plan={plan} cine desde={plan.portada ? DURACION_PORTADA : 0} /> : null}
        </>
      )}

      <Audio src={staticFile(plan.audio)} />
      {plan.musica ? <Audio src={staticFile(`musica/${plan.musica}`)} volume={0.07} loop /> : null}
      <Sonidos plan={plan} />
    </AbsoluteFill>
  );
};
