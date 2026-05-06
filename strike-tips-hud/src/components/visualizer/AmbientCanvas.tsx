import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Stars } from '@react-three/drei';
import * as THREE from 'three';
import { useHUD } from '../../hooks/useHUD';

const AmbientGrid = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const state = useHUD();

  useFrame((root, delta) => {
    // Dynamic Throttle: Only skip frames if CPU is actually peaking right now
    const currentCpu = state.systemHealth.cpu;
    if (currentCpu > 80 && root.clock.elapsedTime % 0.06 < delta) return;

    if (meshRef.current) {
      meshRef.current.rotation.x = Math.PI / 2;
      meshRef.current.position.z = (root.clock.elapsedTime * 0.4) % 1;
    }
  });

  return (
    <mesh ref={meshRef} position={[0, -2, 0]}>
      <planeGeometry args={[100, 100, 16, 16]} />
      <meshStandardMaterial 
        color={state.systemHealth.cpu > 75 ? "#ff0044" : "#6b21a8"} 
        wireframe 
        transparent 
        opacity={0.3} 
        emissive={state.systemHealth.cpu > 75 ? "#550011" : "#220044"}
        emissiveIntensity={3}
      />
    </mesh>
  );
};

const DataParticles = () => {
  const state = useHUD();
  const particleCount = Object.keys(state.events).length * 5 + 30; // Reduced particle count
  
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

  useFrame((root, delta) => {
    // Throttle: Cap at 30fps during load
    if (state.systemHealth.cpu > 50 && root.clock.elapsedTime % 0.06 < delta) return;

    if (pointsRef.current) {
      const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
      for (let i = 0; i < particleCount; i++) {
        positions[i * 3 + 1] += speeds[i] * (state.systemHealth.cpu > 50 ? 1.2 : 1);
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
  // Read if light theme is active by checking document class
  const isLight = document.documentElement.classList.contains('light');
  
  return (
    <div className="absolute inset-0 pointer-events-none z-0">
      <Canvas 
        camera={{ position: [0, 2, 5], fov: 60 }} 
        dpr={[1, 1.5]} 
        gl={{ 
          powerPreference: 'low-power', 
          antialias: false, 
          stencil: false, 
          depth: true,
          alpha: true
        }}
      >
        <fog attach="fog" args={[isLight ? '#f8fafc' : '#000000', 2, 15]} />
        <ambientLight intensity={isLight ? 0.8 : 0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} color={isLight ? "#a855f7" : "#a855f7"} />
        <Float speed={1.5} rotationIntensity={0.4} floatIntensity={0.4}>
          <AmbientGrid />
        </Float>
        <DataParticles />
        <Stars radius={100} depth={50} count={isLight ? 200 : 1000} factor={4} saturation={0} speed={1} />
      </Canvas>
    </div>
  );
};
