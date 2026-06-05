import { useRef, useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

const NODE_COUNT = 24;

export const DreamOrb = () => {
  const { viewport } = useThree();
  const meshRef = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const instancesRef = useRef<THREE.InstancedMesh>(null);
  
  // Calculate dynamic scale based on viewport width
  // Mobile: ~1.8, Tablet: ~2.4, Desktop: ~2.8
  const dynamicScale = useMemo(() => {
    const minScale = 1.6;
    const baseScale = Math.min(2.8, Math.max(minScale, viewport.width * 0.3));
    return baseScale;
  }, [viewport.width]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  
  const nodeData = useMemo(() => {
    return Array.from({ length: NODE_COUNT }, (_, i) => ({
      factor: 2.0 + Math.random() * 1.5,
      speedX: 0.4 + Math.random() * 0.3,
      speedY: 0.3 + Math.random() * 0.2,
      speedZ: 0.5 + Math.random() * 0.2,
      offset: i * (Math.PI * 2 / NODE_COUNT)
    }));
  }, []);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    
    // Main shell
    if (meshRef.current) {
      meshRef.current.rotation.y = time * 0.15;
      meshRef.current.rotation.z = time * 0.1;
      meshRef.current.scale.setScalar(1 + Math.sin(time * 1.5) * 0.03);
    }
    
    // Inner core
    if (coreRef.current) {
      coreRef.current.rotation.y = -time * 0.4;
      coreRef.current.scale.setScalar(0.75 + Math.cos(time * 2.5) * 0.08);
    }

    // Instanced neural nodes
    if (instancesRef.current) {
      nodeData.forEach((node, i) => {
        const t = time + node.offset;
        const x = Math.sin(t * node.speedX) * node.factor;
        const y = Math.cos(t * node.speedY) * node.factor;
        const z = Math.sin(t * node.speedZ) * node.factor;
        
        dummy.position.set(x, y, z);
        const s = 0.06 + Math.sin(time * 2 + i) * 0.02;
        dummy.scale.set(s, s, s);
        dummy.updateMatrix();
        instancesRef.current!.setMatrixAt(i, dummy.matrix);
      });
      instancesRef.current.instanceMatrix.needsUpdate = true;
    }
  });

  return (
    <group scale={dynamicScale}>
      {/* Outer Neural Shell */}
      <mesh ref={meshRef}>
        <icosahedronGeometry args={[1, 12]} />
        <meshStandardMaterial 
          color="#4c1d95" 
          wireframe 
          transparent 
          opacity={0.2} 
          emissive="#6d28d9"
          emissiveIntensity={1.5}
        />
      </mesh>

      {/* Inner Pulsing Core */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[0.5, 32, 32]} />
        <meshStandardMaterial 
          color="#a78bfa" 
          emissive="#8b5cf6" 
          emissiveIntensity={4}
          transparent
          opacity={0.8}
        />
      </mesh>

      {/* Instanced Neural Nodes (Massively optimized) */}
      <instancedMesh ref={instancesRef} args={[undefined, undefined, NODE_COUNT]}>
        <sphereGeometry args={[1, 8, 8]} />
        <meshStandardMaterial 
          color="#c084fc" 
          emissive="#a855f7" 
          emissiveIntensity={8}
          transparent
          opacity={0.9}
        />
      </instancedMesh>
    </group>
  );
};
