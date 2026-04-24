import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Stars } from '@react-three/drei';
import * as THREE from 'three';
import { useHUD } from '../../hooks/useHUD';

const AmbientGrid = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const state = useHUD();
  const isHighLoad = state.systemHealth.cpu > 75;

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = Math.PI / 2;
      // Gently drift the grid
      meshRef.current.position.z = (state.clock.elapsedTime * 0.5) % 1;
    }
  });

  return (
    <mesh ref={meshRef} position={[0, -2, 0]}>
      <planeGeometry args={[100, 100, 40, 40]} />
      <meshStandardMaterial 
        color={isHighLoad ? "#ff0044" : "#6b21a8"} 
        wireframe 
        transparent 
        opacity={0.15} 
        emissive={isHighLoad ? "#550011" : "#110022"}
        emissiveIntensity={2}
      />
    </mesh>
  );
};

const DataParticles = () => {
  const state = useHUD();
  const particleCount = Object.keys(state.events).length * 10 + 50; // Scale with events
  
  const [positions, speeds] = useMemo(() => {
    const pos = new Float32Array(particleCount * 3);
    const spd = new Float32Array(particleCount);
    for (let i = 0; i < particleCount; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 1] = Math.random() * 10;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 20;
      spd[i] = Math.random() * 0.02 + 0.01;
    }
    return [pos, spd];
  }, [particleCount]);

  const pointsRef = useRef<THREE.Points>(null);

  useFrame(() => {
    if (pointsRef.current) {
      const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
      for (let i = 0; i < particleCount; i++) {
        positions[i * 3 + 1] += speeds[i] * (state.systemHealth.cpu > 50 ? 2 : 1);
        if (positions[i * 3 + 1] > 10) {
          positions[i * 3 + 1] = 0;
        }
      }
      pointsRef.current.geometry.attributes.position.needsUpdate = true;
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        {/* @ts-ignore */}
        <bufferAttribute
          attach="attributes-position"
          count={particleCount}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial 
        size={0.05} 
        color={state.systemHealth.status === 'ONLINE' ? "#10b981" : "#f59e0b"} 
        transparent 
        opacity={0.6}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
};

export const AmbientCanvas: React.FC = () => {
  return (
    <div className="absolute inset-0 pointer-events-none z-0">
      <Canvas camera={{ position: [0, 2, 5], fov: 60 }}>
        <fog attach="fog" args={['#000000', 2, 15]} />
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} color="#a855f7" />
        <Float speed={1.5} rotationIntensity={0.5} floatIntensity={0.5}>
          <AmbientGrid />
        </Float>
        <DataParticles />
        <Stars radius={100} depth={50} count={2000} factor={4} saturation={0} fade speed={1} />
      </Canvas>
    </div>
  );
};
