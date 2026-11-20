import React from 'react';
import {Composition} from 'remotion';
import {Video, PlanVideo} from './Video';
import {Video3D} from './Video3D';

const Principal: React.FC<PlanVideo> = (plan) => (plan.motor === '3d' ? <Video3D {...plan} /> : <Video {...plan} />);

const FPS = 30;

const ejemplo: PlanVideo = {
  audio: 'voz_A.wav',
  musica: '',
  subtitulos: true,
  paleta: {fondo: '#FFF4E0', tinta: '#1E1B2E', acentos: ['#FF6B35', '#F7B32B', '#2EC4B6', '#E71D36']},
  escenas: [{componente: 'Ejemplo', inicio: 0, duracion: 4, palabras: [], rotulo: 'Ejemplo'}],
};

export const Root: React.FC = () => (
  <Composition
    id="Video"
    component={Principal as unknown as React.FC<Record<string, unknown>>}
    width={1080}
    height={1920}
    fps={FPS}
    durationInFrames={120}
    defaultProps={ejemplo as unknown as Record<string, unknown>}
    calculateMetadata={({props}) => {
      const plan = props as unknown as PlanVideo;
      const ultima = plan.escenas[plan.escenas.length - 1];
      return {durationInFrames: Math.max(FPS, Math.ceil((ultima.inicio + ultima.duracion) * FPS))};
    }}
  />
);
