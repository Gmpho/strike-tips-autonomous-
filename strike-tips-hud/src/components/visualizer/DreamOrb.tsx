import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export const DreamOrb = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  
  // Custom shader for a neural "dream" look
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uColor: { value: new THREE.Color("#8b5cf6") }
  }), []);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    if (meshRef.current) {
      meshRef.current.rotation.y = time * 0.2;
      meshRef.current.rotation.z = time * 0.15;
      meshRef.current.scale.setScalar(1 + Math.sin(time * 2) * 0.05);
    }
    if (coreRef.current) {
      coreRef.current.rotation.y = -time * 0.5;
      coreRef.current.scale.setScalar(0.8 + Math.cos(time * 3) * 0.1);
    }
    uniforms.uTime.value = time;
  });

  return (
    <group scale={2.5}>
      {/* Outer Neural Shell */}
      <mesh ref={meshRef}>
        <icosahedronGeometry args={[1, 15]} />
        <meshStandardMaterial 
          color="#4c1d95" 
          wireframe 
          transparent 
          opacity={0.3} 
          emissive="#6d28d9"
          emissiveIntensity={2}
        />
      </mesh>

      {/* Inner Pulsing Core */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[0.5, 32, 32]} />
        <meshStandardMaterial 
          color="#a78bfa" 
          emissive="#8b5cf6" 
          emissiveIntensity={5}
          transparent
          opacity={0.8}
        />
      </mesh>

      {/* Floating Sparkles (Neural Nodes) */}
      {[...Array(20)].map((_, i) => (
        <NeuralNode key={i} index={i} />
      ))}
    </group>
  );
};

const NeuralNode = ({ index }: { index: number }) => {
  const mesh = useRef<THREE.Mesh>(null);
  const randomFactor = useMemo(() => Math.random(), []);
  
  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (mesh.current) {
      mesh.current.position.x = Math.sin(t * 0.5 + index) * (2 + randomFactor);
      mesh.current.position.y = Math.cos(t * 0.3 + index * 2) * (2 + randomFactor);
      mesh.current.position.z = Math.sin(t * 0.4 + index * 3) * (2 + randomFactor);
      mesh.current.scale.setScalar(0.05 + Math.sin(t * 2 + index) * 0.02);
    }
  });

  return (
    <mesh ref={mesh}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshStandardMaterial color="#c084fc" emissive="#a855f7" emissiveIntensity={10} />
    </mesh>
  );
};
