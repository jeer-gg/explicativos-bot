// Subtítulos cortos (máximo 3 palabras) con la palabra actual resaltada.
import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {PlanVideo} from './Video';

type Trozo = {inicio: number; fin: number; palabras: {w: string; t: number}[]};

const trocear = (plan: PlanVideo): Trozo[] => {
  const todas = plan.escenas.flatMap((e) => e.palabras.map((p) => ({w: p.w, t: e.inicio + p.t, d: p.d})));
  const trozos: Trozo[] = [];
  let actual: {w: string; t: number}[] = [];
  todas.forEach((p, i) => {
    actual.push({w: p.w, t: p.t});
    const corte = /[.,;:?!¿¡]$/.test(p.w) || actual.length >= 3 || i === todas.length - 1;
    const siguiente = todas[i + 1];
    const pausa = siguiente ? siguiente.t - (p.t + p.d) > 0.35 : true;
    if (corte || pausa) {
      trozos.push({inicio: actual[0].t, fin: siguiente ? siguiente.t : p.t + p.d + 0.4, palabras: actual});
      actual = [];
    }
  });
  return trozos;
};

export const Subtitulos: React.FC<{plan: PlanVideo}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const trozos = React.useMemo(() => trocear(plan), [plan]);
  const trozo = trozos.find((x) => t >= x.inicio && t < x.fin);
  if (!trozo) return null;
  const pop = spring({frame: frame - Math.round(trozo.inicio * fps), fps, config: {damping: 14, stiffness: 220}});
  const resalte = plan.paleta.acentos[1] ?? '#FFD166';

  return (
    <div
      style={{
        position: 'absolute',
        left: 60,
        right: 60,
        bottom: 330,
        textAlign: 'center',
        transform: `scale(${0.85 + 0.15 * pop})`,
      }}
    >
      {trozo.palabras.map((p, i) => {
        const dicha = t >= p.t;
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              margin: '0 12px',
              fontSize: 78,
              fontWeight: 900,
              letterSpacing: -1,
              color: dicha ? resalte : '#FFFFFF',
              WebkitTextStroke: '14px #111',
              paintOrder: 'stroke fill',
              textTransform: 'uppercase',
            }}
          >
            {p.w.replace(/[.,;:]$/, '')}
          </span>
        );
      })}
    </div>
  );
};
