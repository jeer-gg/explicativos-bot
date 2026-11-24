// Escena de ejemplo y referencia de la técnica 2.5D:
// "si el inodoro se queda sonando, casi siempre es el tapón, que deja escapar el agua".
// 3D: el inodoro (se abre y se ve por dentro). 2D: la mano, el agua y las burbujas de la fuga.
import React from 'react';
import {EscenaProps, Flecha, Etiqueta, aparecer, momento, mover} from '../lib3d';
import {Habitacion, Inodoro, Mano, Planta, Sombra} from '../lib25d';

export const Ejemplo25D: React.FC<EscenaProps> = ({frame, fps, duracion, palabras, paleta}) => {
  const [, , resalte] = paleta.acentos;
  const tAbre = momento(palabras, fps, 'tanque', 8);
  const tAdentro = momento(palabras, fps, 'adentro', Math.round(duracion * 0.35));
  const tEscapa = momento(palabras, fps, 'escapa', Math.round(duracion * 0.6));
  const tTapon = momento(palabras, fps, 'tapón', Math.round(duracion * 0.8));

  // La mano entra, agarra la tapa y se la lleva (la tapa sigue a la mano).
  const entra = aparecer(frame, tAbre - 12, 12);
  const lleva = aparecer(frame, tAbre, 16);
  const manoX = mover(frame, [tAbre - 12, tAbre, tAbre + 16], [2.4, 1.0, 1.9]);
  const manoY = mover(frame, [tAbre - 12, tAbre, tAbre + 16], [3.0, 2.9, 4.0]);
  const corte = aparecer(frame, tAdentro, 18);
  const fuga = aparecer(frame, tEscapa, 14);
  const nivel = 0.78 - 0.2 * aparecer(frame, tEscapa, Math.max(20, duracion - tEscapa));
  const senal = aparecer(frame, tTapon, 8);

  return (
    <group>
      <Habitacion />
      <Planta posicion={[-1.6, 0, -1.2]} alto={0.9} frame={frame} fps={fps} />
      <Sombra posicion={[-1.6, 0, -1.2]} radio={0.4} />
      <Inodoro frame={frame} fps={fps} tapa={lleva} corte={corte} nivel={nivel} fuga={fuga} resaltarTapon={senal > 0.5} />
      {entra > 0 && lleva < 1 ? (
        <Mano pose="agarra" posicion={[manoX, manoY, 0.32]} ancho={1.3} frame={frame} fps={fps} escala={entra} />
      ) : null}
      <Flecha desde={[0.6, 2.4, 0.1]} hasta={[-0.05, 1.75, 0]} color={resalte} progreso={senal} />
      <Etiqueta texto="el tapón" punto={[-0.15, 1.64, -0.05]} desplazamiento={[0.55, 0.45, 0.2]} escala={senal} />
    </group>
  );
};
