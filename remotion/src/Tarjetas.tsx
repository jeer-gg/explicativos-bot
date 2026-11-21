// Elementos 2D encima del 3D: título de portada y tarjetas de datos (barras, mitos tachados, contador).
import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import type {PlanVideo, Grafico} from './Video';

const BORDE = '#1B1B1F';
const textoConBorde = (grosor: number): React.CSSProperties => ({
  WebkitTextStroke: `${grosor}px ${BORDE}`,
  paintOrder: 'stroke fill',
  textShadow: `0 ${grosor}px 0 ${BORDE}`,
});

export const DURACION_PORTADA = 1.8;

export const Portada: React.FC<{plan: PlanVideo}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!plan.portada || frame > DURACION_PORTADA * fps) return null;
  const sale = interpolate(frame, [(DURACION_PORTADA - 0.25) * fps, DURACION_PORTADA * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const palabras = plan.portada.split(/\s+/);
  const rojo = '#E5484D';
  let negacion = false;
  return (
    <div style={{position: 'absolute', left: 50, right: 50, top: 290, textAlign: 'center', opacity: sale, transform: `scale(${0.9 + 0.1 * sale})`, lineHeight: 1.02}}>
      {palabras.map((w, i) => {
        if (/^NO$/.test(w)) negacion = true;
        const color = negacion ? rojo : '#FFFFFF';
        return (
          <span key={i} style={{display: 'inline-block', margin: '0 12px', fontSize: palabras.length > 4 ? 108 : 124, fontWeight: 900, color, ...textoConBorde(12)}}>
            {w}
          </span>
        );
      })}
    </div>
  );
};

const Barras: React.FC<{g: Extract<Grafico, {tipo: 'barras'}>; f: number; fps: number; colores: string[]}> = ({g, f, fps, colores}) => {
  const max = Math.max(...g.items.map((i) => i.valor), 1);
  return (
    <div style={{display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 46, height: 380, padding: '0 20px'}}>
      {g.items.map((it, i) => {
        const crece = interpolate(f, [i * 10 + 4, i * 10 + 24], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
        const alto = Math.max(16, (it.valor / max) * 260 * crece);
        const valor = Math.round(it.valor * crece);
        return (
          <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 150}}>
            <div style={{fontSize: 40, fontWeight: 900, color: BORDE, marginBottom: 8, whiteSpace: 'nowrap'}}>
              {valor.toLocaleString('es')} {it.unidad}
            </div>
            <div style={{width: 110, height: alto, background: colores[i % colores.length], border: `6px solid ${BORDE}`, borderRadius: 14}} />
            <div style={{marginTop: 10, fontSize: 30, fontWeight: 800, color: BORDE, textAlign: 'center'}}>{it.etiqueta}</div>
          </div>
        );
      })}
    </div>
  );
};

const Mitos: React.FC<{g: Extract<Grafico, {tipo: 'mitos'}>; f: number; durF: number}> = ({g, f, durF}) => (
  <div style={{display: 'flex', justifyContent: 'center', gap: 34, padding: '10px 0'}}>
    {g.items.map((it, i) => {
      const t0 = 6 + (i * Math.max(12, durF - 20)) / g.items.length;
      const tacha = interpolate(f, [t0, t0 + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
      return (
        <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
          <svg width={170} height={170} viewBox="0 0 170 170">
            <circle cx={85} cy={85} r={74} fill="#FFFFFF" stroke={BORDE} strokeWidth={8} />
            <path d="M45 45 L125 125" stroke="#E5484D" strokeWidth={20} strokeLinecap="round" strokeDasharray={114} strokeDashoffset={114 * (1 - Math.min(1, tacha * 2))} />
            <path d="M125 45 L45 125" stroke="#E5484D" strokeWidth={20} strokeLinecap="round" strokeDasharray={114} strokeDashoffset={114 * (1 - Math.max(0, tacha * 2 - 1))} />
          </svg>
          <div style={{marginTop: 6, fontSize: 40, fontWeight: 900, color: '#FFFFFF', textTransform: 'uppercase', ...textoConBorde(8)}}>{it}</div>
        </div>
      );
    })}
  </div>
);

const Contador: React.FC<{g: Extract<Grafico, {tipo: 'contador'}>; f: number; color: string}> = ({g, f, color}) => {
  const p = interpolate(f, [4, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const n = Math.round(g.valor * p);
  const esAno = g.valor > 1000 && g.valor < 2100 && Number.isInteger(g.valor);
  return (
    <div style={{textAlign: 'center', padding: '10px 40px 22px'}}>
      <div style={{fontSize: 170, fontWeight: 900, color, lineHeight: 1, ...textoConBorde(10)}}>{esAno ? String(n) : n.toLocaleString('es')}</div>
      {g.etiqueta ? <div style={{fontSize: 44, fontWeight: 900, color: BORDE}}>{g.etiqueta}</div> : null}
    </div>
  );
};

export const TarjetaDatos: React.FC<{plan: PlanVideo}> = ({plan}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const e = plan.escenas.find((x) => x.grafico && t >= x.inicio + 0.15 && t < x.inicio + x.duracion);
  if (!e || !e.grafico) return null;
  const f = frame - Math.round((e.inicio + 0.15) * fps);
  const durF = Math.round(e.duracion * fps);
  const pop = spring({frame: f, fps, config: {damping: 13, stiffness: 190}});
  const colores = [plan.paleta.acentos[2], plan.paleta.acentos[0], plan.paleta.acentos[3], plan.paleta.acentos[1]];
  const g = e.grafico;
  const tarjeta = g.tipo !== 'mitos';
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: plan.estilo_subtitulos === 'concepto' ? 590 : 470, display: 'flex', justifyContent: 'center'}}>
      <div
        style={{
          transform: `scale(${0.6 + 0.4 * pop})`,
          opacity: Math.min(1, pop * 1.6),
          background: tarjeta ? '#FFFFFF' : 'transparent',
          border: tarjeta ? `7px solid ${BORDE}` : 'none',
          borderRadius: 40,
          padding: tarjeta ? '26px 34px' : 0,
          boxShadow: tarjeta ? '0 18px 0 rgba(0,0,0,0.18)' : 'none',
        }}
      >
        {g.tipo === 'barras' ? <Barras g={g} f={f} fps={fps} colores={colores} /> : null}
        {g.tipo === 'mitos' ? <Mitos g={g} f={f} durF={durF} /> : null}
        {g.tipo === 'contador' ? <Contador g={g} f={f} color={plan.paleta.acentos[2]} /> : null}
      </div>
    </div>
  );
};
