// Herramientas comunes para las escenas. Claude las usa al dibujar cada escena.
import React from 'react';
import {Easing, interpolate, spring} from 'remotion';

export type Palabra = {w: string; t: number; d: number};
export type Paleta = {fondo: string; tinta: string; acentos: string[]};

export type EscenaProps = {
  frame: number; // fotograma local de la escena (empieza en 0)
  fps: number;
  duracion: number; // duración de la escena en fotogramas
  palabras: Palabra[]; // palabras narradas con su tiempo en segundos (relativo a la escena)
  paleta: Paleta;
  rotulo: string; // 0 a 3 palabras, opcional
};

export const ANCHO = 1080;
export const ALTO = 1920;

const SUAVE = Easing.bezier(0.22, 1, 0.36, 1);

/** 0 → 1 con suavidad entre el fotograma `inicio` y `inicio + dur`. */
export const aparecer = (frame: number, inicio = 0, dur = 14) =>
  interpolate(frame, [inicio, inicio + dur], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: SUAVE,
  });

/** 1 → 0 con suavidad. */
export const desaparecer = (frame: number, inicio: number, dur = 12) => 1 - aparecer(frame, inicio, dur);

/** Rebote elástico 0 → 1 que puede pasarse un poco de 1 (para "pops"). */
export const rebote = (frame: number, fps: number, inicio = 0, rigidez = 140) =>
  spring({frame: frame - inicio, fps, config: {damping: 11, stiffness: rigidez, mass: 0.8}});

/** Oscilación suave para que nada quede quieto. */
export const flotar = (frame: number, amplitud = 8, periodo = 70, fase = 0) =>
  Math.sin((frame / periodo) * Math.PI * 2 + fase) * amplitud;

/** Interpolación con varios puntos, siempre con clamp. */
export const mover = (frame: number, entrada: number[], salida: number[]) =>
  interpolate(frame, entrada, salida, {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: SUAVE});

const normalizar = (s: string) =>
  s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9ñ]/g, '');

/** Fotograma en que se pronuncia una palabra (para sincronizar la animación con la voz). */
export const momento = (palabras: Palabra[], fps: number, texto: string, defecto = 0): number => {
  const buscada = normalizar(texto);
  if (!buscada) return defecto;
  const p = palabras.find((x) => normalizar(x.w).includes(buscada) || buscada.includes(normalizar(x.w)) && normalizar(x.w).length > 3);
  return p ? Math.round(p.t * fps) : defecto;
};

/** Sombra plana elíptica bajo un objeto. */
export const Sombra: React.FC<{x: number; y: number; ancho: number; color?: string}> = ({x, y, ancho, color = '#000'}) => (
  <ellipse cx={x} cy={y} rx={ancho / 2} ry={ancho / 9} fill={color} opacity={0.14} />
);

/** Propiedades de contorno grueso del estilo del canal. */
export const contorno = (tinta: string, grosor = 7) => ({
  stroke: tinta,
  strokeWidth: grosor,
  strokeLinejoin: 'round' as const,
  strokeLinecap: 'round' as const,
});

/** Escena de respaldo si una escena generada falla. Sencilla pero animada. */
export const EscenaRespaldo: React.FC<EscenaProps> = ({frame, fps, paleta, rotulo}) => {
  const [a1, a2, a3, a4] = paleta.acentos;
  const pop = rebote(frame, fps, 4);
  return (
    <svg width={ANCHO} height={ALTO} viewBox={`0 0 ${ANCHO} ${ALTO}`}>
      <rect width={ANCHO} height={ALTO} fill={paleta.fondo} />
      {[a1, a2, a3, a4].map((c, i) => (
        <circle
          key={i}
          cx={200 + i * 230}
          cy={760 + flotar(frame, 30, 50 + i * 9, i)}
          r={60 + i * 12}
          fill={c}
          opacity={0.85}
          style={{transform: `scale(${aparecer(frame, i * 4)})`, transformBox: 'fill-box', transformOrigin: 'center'}}
          {...contorno(paleta.tinta)}
        />
      ))}
      <g transform={`translate(540 1080) scale(${pop})`}>
        <rect x={-420} y={-110} width={840} height={220} rx={40} fill="#fff" {...contorno(paleta.tinta, 9)} />
        <text x={0} y={30} textAnchor="middle" fontSize={96} fontWeight={900} fill={paleta.tinta}>
          {rotulo || '¿Sabías esto?'}
        </text>
      </g>
    </svg>
  );
};
