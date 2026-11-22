// Subtítulos cortos (máximo 3 palabras) con la palabra actual resaltada.
import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {EscenaPlan, PlanVideo} from './Video';

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

// ---------- Estilo "concepto" (como los Reels 3D más virales) ----------
// En vez de subtitular cada palabra, arriba aparece solo el CONCEPTO de cada momento
// («EL FLOTADOR», «LA BOLA SUBE», «NO SUBE SOLA»), palabra por palabra justo cuando la voz lo
// dice, y se queda hasta el siguiente. Lo negativo va en rojo y la palabra clave en el color de resalte.

type Concepto = {inicio: number; fin: number; palabras: {w: string; t: number}[]; clave: string};

const NEGACION = /^(no|sin|nunca|ni|jamas|tampoco|nadie|nada)$/;

const parecida = (a: string, b: string) =>
  a.length > 0 && b.length > 0 && (a === b || (a.length > 3 && b.length > 3 && (a.startsWith(b) || b.startsWith(a))));

const momentosConcepto = (e: EscenaPlan): Concepto | null => {
  const texto = (e.concepto || e.rotulo || '').trim();
  if (!texto) return null;
  const palabras = texto.split(/\s+/).filter(Boolean).slice(0, 5);
  const objetivo = palabras.map(normal);
  const dichas = e.palabras.map((p) => normal(p.w));
  // Busca la frase en la voz: el primer sitio donde coinciden en orden la mayoría de sus palabras.
  let tiempos: number[] | null = null;
  for (let j = 0; j < dichas.length && !tiempos; j++) {
    if (!parecida(dichas[j], objetivo[0]) && !(objetivo.length > 1 && parecida(dichas[j], objetivo[1]))) continue;
    const desfase = parecida(dichas[j], objetivo[0]) ? 0 : 1;
    const ts: number[] = [];
    let k = j;
    let aciertos = 0;
    objetivo.forEach((w, i) => {
      if (i < desfase) {
        ts.push(Math.max(0, e.palabras[j].t - 0.12));
        return;
      }
      const hasta = Math.min(dichas.length, k + 3);
      let hallado = -1;
      for (let m = k; m < hasta; m++) if (parecida(dichas[m], w)) { hallado = m; break; }
      if (hallado >= 0) {
        ts.push(e.palabras[hallado].t);
        k = hallado + 1;
        aciertos++;
      } else {
        ts.push((ts[ts.length - 1] ?? e.palabras[j].t) + 0.14);
      }
    });
    if (aciertos >= Math.ceil((objetivo.length - desfase) / 2)) tiempos = ts;
  }
  if (!tiempos) {
    // No se dice tal cual: aparece en la palabra clave (o al empezar la escena), una tras otra.
    const base = e.clave != null ? e.clave : 0.15;
    tiempos = objetivo.map((_, i) => base + i * 0.14);
  }
  const absolutos = tiempos.map((x) => e.inicio + Math.max(0, x));
  return {
    inicio: absolutos[0] - 0.04,
    fin: e.inicio + e.duracion,
    palabras: palabras.map((w, i) => ({w, t: absolutos[i]})),
    clave: normal(e.clave_palabra ?? ''),
  };
};

export const Conceptos: React.FC<{plan: PlanVideo; oscuro?: boolean; desde?: number}> = ({plan, oscuro = false, desde = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const conceptos = React.useMemo(() => plan.escenas.map(momentosConcepto).filter((c): c is Concepto => c !== null), [plan]);
  if (t < desde) return null;
  const c = conceptos.find((x) => t >= x.inicio && t < x.fin);
  if (!c) return null;
  const largo = c.palabras.reduce((n, p) => n + p.w.length + 1, 0);
  const tam = largo <= 12 ? 120 : largo <= 20 ? 100 : largo <= 28 ? 84 : 72;
  const tinta = oscuro ? '#FFFFFF' : '#1B1B1F';
  const borde = oscuro ? '#0E0E12' : '#FFFFFF';
  // Palabra clave: azul sobre fondo claro (legible) y el resalte vivo sobre fondo oscuro
  const resalte = oscuro ? plan.paleta.acentos[2] ?? '#A3D92B' : '#1F6FD1';
  let negado = false;
  return (
    <div style={{position: 'absolute', left: 36, right: 36, top: 292, textAlign: 'center', lineHeight: 1.02}}>
      {c.palabras.map((p, i) => {
        const n = normal(p.w);
        if (NEGACION.test(n)) negado = true;
        const f = frame - Math.round(p.t * fps);
        if (f < 0) return null;
        const sube = spring({frame: f, fps, config: {damping: 15, stiffness: 260}});
        const esClave = !negado && c.clave.length > 2 && parecida(n, c.clave);
        const color = negado ? '#E5484D' : esClave ? resalte : tinta;
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              margin: `0 ${Math.round(tam * 0.11)}px`,
              fontSize: tam,
              fontWeight: 900,
              letterSpacing: -1,
              textTransform: 'uppercase',
              color,
              opacity: Math.min(1, sube * 1.6),
              transform: `translateY(${(1 - sube) * 46}px) scale(${0.86 + 0.14 * sube})`,
              WebkitTextStroke: `${oscuro ? 10 : 8}px ${borde}`,
              paintOrder: 'stroke fill',
            }}
          >
            {p.w.replace(/[.,;:!?¡¿«»"]/g, '')}
          </span>
        );
      })}
    </div>
  );
};
