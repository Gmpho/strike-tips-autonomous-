import React from 'react';

export const AmbientCanvas: React.FC = () => {
  return (
    <div className="absolute inset-0 pointer-events-none z-0 animate-fade-in"
      style={{
        background: 'radial-gradient(ellipse at center, rgba(168,85,247,0.06) 0%, transparent 70%)'
      }}
    />
  );
};
