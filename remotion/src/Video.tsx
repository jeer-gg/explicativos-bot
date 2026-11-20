// Video completo: un solo plano continuo. Las escenas están repartidas sobre un
// "tablero" grande y la cámara viaja de una a otra sin cortes.
import React from 'react';
import {AbsoluteFill, Audio, Easing, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Nunito';
import {ANCHO, ALTO, EscenaRespaldo, Palabra, Paleta} from './lib';
import {ESCENAS} from './escenas';
import {Subtitulos} from './Subtitulos';

const {fontFamily} = loadFont('normal', {weights: ['700', '800', '900'], subsets: ['latin', 'latin-ext']});

export type EscenaPlan = {
  componente: string;
  inicio: number; // segundos
  duracion: number; // segundos
  palabras: Palabra[];
  rotulo: string;
};

export type PlanVideo = {
  audio: string;
  musica: string;
  subtitulos: boolean;
  paleta: Paleta;
  escenas: EscenaPlan[];
};

// Posición de cada escena en el tablero: avanza a la derecha en zigzag.
const posicion = (i: number) => ({x: i * (ANCHO + 120), y: i % 2 === 0 ? 0 : -300});

const SUAVE = Easing.bezier(0.65, 0, 0.35, 1);

const camara = (frame: number, fps: number, plan: PlanVideo) => {
  const T = Math.round(0.55 * fps); // duración del viaje entre escenas
  const inicios = plan.escenas.map((e) => Math.round(e.inicio * fps));
  let actual = 0;
  for (let i = 0; i < inicios.length; i++) if (frame >= inicios[i] - Math.round(T * 0.4)) actual = i;
  const llegada = inicios[actual] - Math.round(T * 0.4);
  const p = actual === 0 ? 1 : interpolate(frame, [llegada, llegada + T], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: SUAVE,
  });
  const desde = posicion(Math.max(0, actual - 1));
  const hasta = posicion(actual);
  const durEsc = Math.round(plan.escenas[actual].duracion * fps);
  const local = Math.max(0, frame - inicios[actual]);
  // Se aleja un poco en el viaje (nunca demasiado) y se acerca despacio dentro de la escena.
  const viaje = 1 - 0.13 * Math.sin(Math.PI * p);
  const acercar = 1 + 0.035 * Math.min(1, local / Math.max(1, durEsc));
  return {
    x: desde.x + (hasta.x - desde.x) * p,
    y: desde.y + (hasta.y - desde.y) * p,
    zoom: viaje * acercar,
    actual,
    inicios,
  };
};

export const Video: React.FC<PlanVideo> = (plan) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cam = camara(frame, fps, plan);
  const visibles = [cam.actual - 1, cam.actual, cam.actual + 1].filter((i) => i >= 0 && i < plan.escenas.length);

  return (
    <AbsoluteFill style={{backgroundColor: plan.paleta.fondo, fontFamily, overflow: 'hidden'}}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: ANCHO,
          height: ALTO,
          transformOrigin: '0 0',
          transform: `translate(${ANCHO / 2}px, ${ALTO / 2}px) scale(${cam.zoom}) translate(${-(cam.x + ANCHO / 2)}px, ${-(cam.y + ALTO / 2)}px)`,
        }}
      >
        {/* Tablero con puntos: hace visible el movimiento de la cámara */}
        <div
          style={{
            position: 'absolute',
            left: -2000,
            top: -2600,
            width: plan.escenas.length * (ANCHO + 120) + 4000,
            height: ALTO + 5200,
            backgroundImage: `radial-gradient(${plan.paleta.tinta}22 3px, transparent 3.5px)`,
            backgroundSize: '64px 64px',
          }}
        />
        {visibles.map((i) => {
          const e = plan.escenas[i];
          const Escena = ESCENAS[e.componente] ?? EscenaRespaldo;
          const pos = posicion(i);
          const local = Math.max(0, frame - cam.inicios[i]);
          return (
            <div key={i} style={{position: 'absolute', left: pos.x, top: pos.y, width: ANCHO, height: ALTO, borderRadius: 48, overflow: 'hidden'}}>
              <Escena
                frame={local}
                fps={fps}
                duracion={Math.round(e.duracion * fps)}
                palabras={e.palabras}
                paleta={plan.paleta}
                rotulo={e.rotulo}
              />
            </div>
          );
        })}
      </div>

      {plan.subtitulos ? <Subtitulos plan={plan} /> : null}

      <Audio src={staticFile(plan.audio)} />
      {plan.musica ? <Audio src={staticFile(`musica/${plan.musica}`)} volume={0.07} loop /> : null}
      {plan.escenas.slice(1).map((e, i) => (
        <Sequence key={i} from={Math.max(0, Math.round((e.inicio - 0.3) * fps))} durationInFrames={Math.round(0.6 * fps)}>
          <Audio src={staticFile('sfx/whoosh.mp3')} volume={0.32} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
