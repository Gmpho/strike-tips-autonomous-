import * as THREE from 'three';

export class VisualEngine {
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private container: HTMLElement;
  private points: THREE.Points;

  constructor(containerId: string) {
    this.container = document.getElementById(containerId)!;
    this.scene = new THREE.Scene();
    
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    this.camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    this.camera.position.z = 5;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);

    // Create Intelligence Mesh (Floating Particles)
    const geometry = new THREE.BufferGeometry();
    const count = 1500;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    for (let i = 0; i < count * 3; i++) {
      positions[i] = (Math.random() - 0.5) * 15;
      // Purple / Blue Intelligence Palette
      colors[i] = i % 3 === 0 ? 0.66 : i % 3 === 1 ? 0.33 : 0.97; 
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 0.02,
      vertexColors: true,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending
    });

    this.points = new THREE.Points(geometry, material);
    this.scene.add(this.points);

    window.addEventListener('resize', () => this.onResize());
  }

  start() {
    const animate = () => {
      requestAnimationFrame(animate);
      
      // Subtle organic motion
      this.points.rotation.y += 0.0005;
      this.points.rotation.x += 0.0002;
      
      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }

  updateData(events: Record<string, any>) {
    const eventList = Object.values(events);
    const count = eventList.length;

    // Scale rotation speed with number of active events
    this.points.rotation.y = 0.0005 + count * 0.0001;
    this.points.rotation.x = 0.0002 + count * 0.00005;

    // Recolour particles based on average edge: high edge → green, low → purple
    const avgEdge = count > 0
      ? eventList.reduce((sum, e) => sum + (e.runners?.[0]?.edge ?? 0), 0) / count
      : 0;
    const t = Math.min(avgEdge / 20, 1); // normalise 0–20% edge to 0–1

    const colors = (this.points.geometry.attributes.color as THREE.BufferAttribute).array as Float32Array;
    for (let i = 0; i < colors.length; i += 3) {
      colors[i]     = 0.66 - t * 0.66; // R: fade out red
      colors[i + 1] = t * 0.85;        // G: grow green
      colors[i + 2] = 0.97 - t * 0.5;  // B: slight fade
    }
    this.points.geometry.attributes.color.needsUpdate = true;
  }

  private onResize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }
}
