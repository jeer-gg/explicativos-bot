// Este archivo lo reescribe el bot en cada video.
import type React from 'react';
import type {EscenaProps} from '../lib';
import {Ejemplo} from './Ejemplo';

export const ESCENAS: Record<string, React.FC<EscenaProps>> = {
  Ejemplo,
};
