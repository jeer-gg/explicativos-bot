// Escena 3D de ejemplo y referencia (formato "pieza por pieza"):
// "un banco de tres patas nunca cojea, porque tres puntos siempre caben en un mismo plano".
// Las escenas 3D que genera Claude siguen esta misma forma.
import React from 'react';
import {EscenaProps, Pieza, Etiqueta, Medida, Flecha, Ojos, Aro, caer, aparecer, rebote, flotar, mover, momento} from '../lib3d';

export const Ejemplo3D: React.FC<EscenaProps> = ({frame, fps, duracion, palabras, paleta}) => {
  const [principal, secundario, resalte, extra] = paleta.acentos;
  const madera = '#C98B4F';
  const maderaOscura = '#9C6535';

  // Golpes sincronizados con la voz (con valor por defecto si la palabra no aparece).
  const tPatas = momento(palabras, fps, 'patas', 4);
  const tAsiento = momento(palabras, fps, 'asiento', Math.round(duracion * 0.35));
  const tPlano = momento(palabras, fps, 'plano', Math.round(duracion * 0.6));
  const tCojea = momento(palabras, fps, 'cojea', Math.round(duracion * 0.8));

  // Las tres patas caen una tras otra; luego el asiento.
  const patas = [0, 1, 2].map((i) => {
    const ang = (i / 3) * Math.PI * 2 + Math.PI / 6;
    return {x: Math.cos(ang) * 0.42, z: Math.sin(ang) * 0.42, ang, anim: caer(frame, fps, tPatas + i * 5)};
  });
  const asiento = caer(frame, fps, tAsiento, 1.6);
  const balanceo = Math.sin(frame / 6) * 0.04 * aparecer(frame, tCojea, 6); // tiembla el piso, el banco no
  const triangulo = aparecer(frame, tPlano, 14);
  const salto = rebote(frame, fps, tCojea);

  return (
    <group>
      {/* Capa trasera: una mesa de cuatro patas que SÍ cojea (contraste) */}
      <group position={[-1.9, 0, -2.6]} rotation={[0, 0.5, balanceo * 2]}>
        <Pieza forma="caja" medidas={[1.2, 0.08, 0.8]} color={secundario} posicion={[0, 0.75, 0]} />
        {[[-0.5, -0.32], [0.5, -0.32], [-0.5, 0.32], [0.5, 0.32]].map(([x, z], i) => (
          <Pieza key={i} forma="caja" medidas={[0.07, 0.72, 0.07]} color={secundario} posicion={[x, 0.36, z]} />
        ))}
      </group>
      <Pieza forma="caja" medidas={[0.5, 0.04, 0.5]} color={extra} posicion={[1.6, 0.02, -1.4]} rotacion={[0, 0.4, 0]} />

      {/* Capa media: el banco que se arma pieza por pieza */}
      <group rotation={[0, flotar(frame, 0.08, 120), 0]}>
        {patas.map((p, i) => (
          <Pieza
            key={i}
            forma="cilindro"
            medidas={[0.045, 0.055, 0.7]}
            color={maderaOscura}
            posicion={[p.x, 0.35 + p.anim.y, p.z]}
            rotacion={[Math.sin(p.ang) * 0.12, 0, -Math.cos(p.ang) * 0.12 + p.anim.giro]}
            escala={p.anim.escala}
          />
        ))}
        <group position={[0, 0.74 + asiento.y + 0.05 * salto, 0]} rotation={[0, 0, asiento.giro]} scale={asiento.escala}>
          <Pieza forma="cilindro" medidas={[0.55, 0.55, 0.09]} color={madera} />
          <Ojos posicion={[0, 0.0, 0.53]} tam={0.07} mirar={[mover(frame, [tPlano, tPlano + 10], [0, -0.8]), -0.3]} frame={frame} />
        </group>
        {/* Tres puntos de apoyo y el triángulo que forman */}
        {patas.map((p, i) => (
          <Aro key={i} posicion={[p.x * 1.12, 0, p.z * 1.12]} radio={0.07} color={resalte} progreso={triangulo} />
        ))}
        {patas.map((p, i) => {
          const q = patas[(i + 1) % 3];
          return (
            <Flecha key={`f${i}`} desde={[p.x * 1.12, 0.02, p.z * 1.12]} hasta={[q.x * 1.12, 0.02, q.z * 1.12]} color={resalte} grosor={0.018} progreso={mover(frame, [tPlano + i * 4, tPlano + i * 4 + 10], [0, 1])} />
          );
        })}
      </group>

      {/* Etiquetas y medida */}
      <Etiqueta texto="3 patas" punto={[patas[0].x, 0.3, patas[0].z]} desplazamiento={[0.55, 0.35, 0.2]} escala={aparecer(frame, tPatas + 12, 8)} />
      <Etiqueta texto="asiento" punto={[0.3, 0.8, 0.3]} desplazamiento={[0.5, 0.5, 0]} escala={aparecer(frame, tAsiento + 6, 8)} />
      <Medida desde={[-0.75, 0, 0.6]} hasta={[-0.75, 0.79, 0.6]} texto="45 cm" progreso={aparecer(frame, tAsiento + 10, 12)} />

      {/* Capa delantera: objeto cercano que da profundidad */}
      <Pieza forma="cilindro" medidas={[0.12, 0.1, 0.22]} color={principal} posicion={[0.95, 0.11, 1.2]} />
    </group>
  );
};
