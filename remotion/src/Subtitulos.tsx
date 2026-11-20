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

const normal = (s: string) => s.toLowerCase().normalize('NFD').replace(/[^a-z0-9ñ]/g, '');

export const Subtitulos: React.FC<{plan: PlanVideo; cine?: boolean; titular?: boolean; desde?: number}> = ({plan, cine = false, titular = false, desde = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const trozos = React.useMemo(() => trocear(plan), [plan]);
  const trozo = trozos.find((x) => t >= x.inicio && t < x.fin);
  if (!trozo || t < desde) return null;
  const pop = spring({frame: frame - Math.round(trozo.inicio * fps), fps, config: {damping: 14, stiffness: 220}});
  const resalte = plan.paleta.acentos[1] ?? '#FFD166';

  if (titular) {
    // Estilo titular (3D de día): arriba, mayúsculas grandes con contorno; la palabra clave en color.
    const claves = plan.escenas.map((e) => normal(e.clave_palabra ?? '')).filter((c) => c.length > 2);
    const color = plan.paleta.acentos[2] ?? '#2F7DE1';
    return (
      <div style={{position: 'absolute', left: 40, right: 40, top: 300, textAlign: 'center', transform: `scale(${0.85 + 0.15 * pop})`, lineHeight: 1.05}}>
        {trozo.palabras.map((p, i) => {
          const n = normal(p.w);
          const esClave = claves.some((c) => n === c || (n.length > 3 && (c.includes(n) || n.includes(c))));
          const dicha = t >= p.t - 0.05;
          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                margin: '0 10px',
                fontSize: 96,
                fontWeight: 900,
                textTransform: 'uppercase',
                color: esClave ? color : '#FFFFFF',
                opacity: dicha ? 1 : 0.35,
                WebkitTextStroke: '11px #1B1B1F',
                paintOrder: 'stroke fill',
                textShadow: '0 9px 0 #1B1B1F',
              }}
            >
              {p.w.replace(/[.,;:]$/, '')}
            </span>
          );
        })}
      </div>
    );
  }

  if (cine) {
    // Estilo cine (videos 3D): arriba, letra normal, la palabra que suena dentro de una cajita de color.
    const luz = plan.paleta.acentos[2] ?? '#FFC27A';
    return (
      <div style={{position: 'absolute', left: 70, right: 70, top: 318, textAlign: 'center', transform: `translateY(${(1 - pop) * 14}px)`, opacity: Math.min(1, pop * 1.4)}}>
        {trozo.palabras.map((p, i) => {
          const dicha = t >= p.t;
          const actual = dicha && (i === trozo.palabras.length - 1 || t < trozo.palabras[i + 1].t);
          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                margin: '0 6px',
                padding: '2px 14px 6px',
                borderRadius: 14,
                fontSize: 70,
                fontWeight: 900,
                letterSpacing: -0.5,
                color: actual ? '#141414' : dicha ? '#FFFFFF' : 'rgba(255,255,255,0.55)',
                background: actual ? luz : 'transparent',
                textShadow: actual ? 'none' : '0 4px 18px rgba(0,0,0,0.65)',
              }}
            >
              {p.w}
            </span>
          );
        })}
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'absolute',
        left: 60,
        right: 60,
        bottom: 380,
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
              fontSize: 84,
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
