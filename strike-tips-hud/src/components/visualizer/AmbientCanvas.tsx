import { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Stars } from '@react-three/drei';
import * as THREE from 'three';
import { useHUD } from '../../hooks/useHUD';

// Suppress unhandled Three.js/WebGL promise rejections globally
if (typeof window !== 'undefined' && !(window as any).__threeRejectionHandlerAttached) {
  (window as any).__threeRejectionHandlerAttached = true;
  window.addEventListener('unhandledrejection', (e: PromiseRejectionEvent) => {
    const msg = String(e.reason ?? '');
    if (msg.includes('three') || msg.includes('WebGL') || msg.includes('webgl')) {
      e.preventDefault();
    }
  });
}

const AmbientGrid = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const state = useHUD();

  useFrame((root) => {
    if (meshRef.current) {
      meshRef.current.position.z = (root.clock.elapsedTime * 0.4) % 1;
    }
  });

  const isHighLoad = state.systemHealth.cpu > 75;

  return (
    <mesh ref={meshRef} position={[0, -2, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[100, 100, 16, 16]} />
      <meshStandardMaterial 
        color={isHighLoad ? "#ff0044" : "#6b21a8"} 
        wireframe 
        transparent 
        opacity={0.2} 
        emissive={isHighLoad ? "#550011" : "#220044"}
        emissiveIntensity={isHighLoad ? 1 : 2}
      />
    </mesh>
  );
};

const DataParticles = () => {
  const state = useHUD();
  const particleCount = useMemo(() => Object.keys(state.events).length * 5 + 30, [state.events]);
  
  const [positions, speeds] = useMemo(() => {
    const pos = new Float32Array(particleCount * 3);
    const spd = new Float32Array(particleCount);
    for (let i = 0; i < particleCount; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 10;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 20;
      spd[i] = Math.random() * 0.02 + 0.01;
    }
    return [pos, spd];
  }, [particleCount]);

  const pointsRef = useRef<THREE.Points>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uColor: { value: new THREE.Color("#10b981") },
    uOpacity: { value: 0.6 }
  }), []);

  useFrame((root) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = root.clock.elapsedTime;
      materialRef.current.uniforms.uColor.value.set(state.systemHealth.status === 'ONLINE' ? "#10b981" : "#f59e0b");
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
        <bufferAttribute
          attach="attributes-speed"
          args={[speeds, 1]}
        />
      </bufferGeometry>
      <shaderMaterial
        ref={materialRef}
        transparent
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        uniforms={uniforms}
        vertexShader={`
          uniform float uTime;
          attribute float speed;
          varying float vOpacity;
          void main() {
            vec3 pos = position;
            pos.y = mod(pos.y + uTime * speed * 2.0 + 5.0, 10.0) - 5.0;
            vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
            gl_PointSize = 6.0 * (1.0 / -mvPosition.z);
            gl_Position = projectionMatrix * mvPosition;
            vOpacity = 1.0 - abs(pos.y / 5.0);
          }
        `}
        fragmentShader={`
          uniform vec3 uColor;
          uniform float uOpacity;
          varying float vOpacity;
          void main() {
            gl_FragColor = vec4(uColor, vOpacity * uOpacity);
          }
        `}
      />
    </points>
  );
};

function webglSupported(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

export const AmbientCanvas: React.FC = () => {
  const [hasWebgl] = useState(webglSupported);
  const [isWebgpuActive, setIsWebgpuActive] = useState(false);

  useEffect(() => {
    const handleWebGPUActivity = (e: Event) => {
      const active = (e as CustomEvent).detail?.active ?? false;
      setIsWebgpuActive(active);
    };
    window.addEventListener('webgpu-activity', handleWebGPUActivity);
    return () => {
      window.removeEventListener('webgpu-activity', handleWebGPUActivity);
    };
  }, []);

  if (!hasWebgl || isWebgpuActive) {
    return (
      <div className="absolute inset-0 pointer-events-none z-0"
        style={{
          background: 'radial-gradient(ellipse at center, rgba(168,85,247,0.06) 0%, transparent 70%)'
        }}
      />
    );
  }

  // Read if light theme is active by checking document class
  const isLight = document.documentElement.classList.contains('light');
  
  return (
    <div className="absolute inset-0 pointer-events-none z-0">
      <Canvas 
        camera={{ position: [0, 2, 5], fov: 60 }} 
        dpr={[1, 2]} // High-DPI support for Retina displays
        gl={{ 
          powerPreference: 'low-power', 
          antialias: false, 
          stencil: false, 
          depth: true,
          alpha: true,
          preserveDrawingBuffer: false,
          failIfMajorPerformanceCaveat: false
        }}
        onCreated={(state) => {
          state.gl.domElement.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            console.warn('[WebGL] Context lost. Attempting restoration...');
          });
          state.gl.domElement.addEventListener('webglcontextrestored', () => {
            console.log('[WebGL] Context restored.');
          });
        }}
      >
        <fog attach="fog" args={[isLight ? '#f8fafc' : '#000000', 2, 15]} />
        <ambientLight intensity={isLight ? 0.8 : 0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} color="#a855f7" />
        <Float speed={1.2} rotationIntensity={0.3} floatIntensity={0.3}>
          <AmbientGrid />
        </Float>
        <DataParticles />
        <Stars radius={100} depth={50} count={isLight ? 200 : 800} factor={4} saturation={0} speed={1} />
      </Canvas>
    </div>
  );
};
