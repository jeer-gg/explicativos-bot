// Escena de ejemplo y referencia de estilo: "el pan se pone duro porque pierde agua".
// Las escenas que genera Claude siguen esta misma forma.
import React from 'react';
import {EscenaProps, ANCHO, ALTO, aparecer, rebote, flotar, mover, momento, Sombra, contorno} from '../lib';

export const Ejemplo: React.FC<EscenaProps> = ({frame, fps, duracion, palabras, paleta, rotulo}) => {
  const [naranja, amarillo, turquesa, rojo] = paleta.acentos;
  const tinta = paleta.tinta;
  const c = contorno(tinta);

  // Momentos sincronizados con la voz (con valores por defecto si la palabra no aparece).
  const tAgua = momento(palabras, fps, 'agua', 30);
  const tDuro = momento(palabras, fps, 'duro', Math.round(duracion * 0.6));

  const entrada = rebote(frame, fps, 2);
  const respira = 1 + flotar(frame, 0.015, 50);
  const dureza = aparecer(frame, tDuro, 18); // 0 = pan blando, 1 = pan duro
  const ceja = mover(frame, [tDuro, tDuro + 10], [0, -14]);

  // Gotitas de agua que escapan del pan, cada una con su retraso.
  const gotas = [0, 1, 2, 3, 4, 5].map((i) => {
    const inicio = tAgua + i * 7;
    const p = aparecer(frame, inicio, 40);
    return {
      x: 420 + i * 48 + flotar(frame, 12, 40, i),
      y: 980 - p * 520,
      op: p > 0 && p < 1 ? 1 - p * 0.8 : 0,
      s: 0.6 + (i % 3) * 0.2,
    };
  });

  return (
    <svg width={ANCHO} height={ALTO} viewBox={`0 0 ${ANCHO} ${ALTO}`}>
      {/* Fondo: cocina con ventana y repisa */}
      <rect width={ANCHO} height={ALTO} fill={paleta.fondo} />
      <rect x={140} y={260} width={380} height={300} rx={24} fill="#fff" {...c} />
      <line x1={330} y1={260} x2={330} y2={560} {...c} />
      <circle cx={430 + flotar(frame, 10, 120)} cy={340} r={34} fill={amarillo} {...contorno(tinta, 5)} />
      <rect x={640} y={420} width={300} height={22} rx={10} fill={turquesa} {...c} />
      <rect x={680} y={330} width={70} height={90} rx={12} fill={rojo} {...contorno(tinta, 5)} />
      <rect x={780} y={350} width={60} height={70} rx={12} fill={amarillo} {...contorno(tinta, 5)} />

      {/* Mesa */}
      <rect x={-20} y={1260} width={ANCHO + 40} height={700} fill={naranja} {...c} />
      <rect x={-20} y={1260} width={ANCHO + 40} height={40} fill={tinta} opacity={0.15} />
      <Sombra x={540} y={1250} ancho={560} />

      {/* El pan, con cara: entra con rebote y se arruga al volverse duro */}
      <g transform={`translate(540 1060) scale(${entrada * respira} ${entrada * (respira - dureza * 0.08)})`}>
        <path
          d="M -260 160 Q -280 -40 -150 -110 Q 0 -190 150 -110 Q 280 -40 260 160 Z"
          fill={dureza > 0.5 ? '#C8873A' : '#E9A85C'}
          {...c}
        />
        {[-120, -10, 100].map((x, i) => (
          <path key={i} d={`M ${x} -100 q 30 50 60 0`} fill="none" {...contorno(tinta, 6)} opacity={0.7} />
        ))}
        {/* Grietas que aparecen al endurecerse */}
        <path d="M -180 60 l 40 -30 l 20 30 l 40 -25" fill="none" {...contorno(tinta, 5)} opacity={dureza} />
        {/* Cara */}
        <circle cx={-70} cy={30} r={16} fill={tinta} />
        <circle cx={70} cy={30} r={16} fill={tinta} />
        <path d={`M -95 ${-10 + ceja} l 50 ${-ceja * 0.6}`} {...contorno(tinta, 6)} />
        <path d={`M 95 ${-10 + ceja} l -50 ${-ceja * 0.6}`} {...contorno(tinta, 6)} />
        <path d={dureza > 0.5 ? 'M -40 90 q 40 -25 80 0' : 'M -40 80 q 40 35 80 0'} fill="none" {...contorno(tinta, 6)} />
      </g>

      {/* Gotitas de agua escapando */}
      {gotas.map((g, i) => (
        <path
          key={i}
          d="M 0 -30 Q 22 0 0 18 Q -22 0 0 -30 Z"
          transform={`translate(${g.x} ${g.y}) scale(${g.s})`}
          fill={turquesa}
          opacity={g.op}
          {...contorno(tinta, 5)}
        />
      ))}

      {/* Rótulo corto */}
      {rotulo ? (
        <g opacity={aparecer(frame, 8)} transform={`translate(540 ${700 + flotar(frame, 6, 60)})`}>
          <rect x={-200} y={-60} width={400} height={100} rx={28} fill="#fff" {...c} />
          <text x={0} y={8} textAnchor="middle" fontSize={56} fontWeight={900} fill={tinta}>{rotulo}</text>
        </g>
      ) : null}
    </svg>
  );
};
