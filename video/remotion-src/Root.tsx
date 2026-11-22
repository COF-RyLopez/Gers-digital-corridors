import React from 'react';
import {Composition} from 'remotion';
import {MyComposition} from './Composition';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Corridor"
      component={MyComposition}
      durationInFrames={2670}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
