import * as THREE from 'three';

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) {
        console.error('Canvas not found');
        return;
    }

    const scene = new THREE.Scene();
    scene.background = null;
    
    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 0, 5);
    
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    
    // Тор
    const geometry = new THREE.TorusGeometry(1.3, 0.25, 64, 200);
    const material = new THREE.MeshStandardMaterial({
        color: 0xff3366,
        emissive: 0x441122,
        metalness: 0.9,
        roughness: 0.1,
        transparent: true
    });
    const torus = new THREE.Mesh(geometry, material);
    scene.add(torus);
    
    // Частицы
    const particles = [];
    const particleGeo = new THREE.SphereGeometry(0.04, 8, 8);
    
    for (let i = 0; i < 200; i++) {
        const particleMat = new THREE.MeshStandardMaterial({ color: 0xff6699 });
        const particle = new THREE.Mesh(particleGeo, particleMat);
        
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const radius = 2.5;
        particle.position.x = radius * Math.sin(phi) * Math.cos(theta);
        particle.position.y = radius * Math.sin(phi) * Math.sin(theta);
        particle.position.z = radius * Math.cos(phi);
        
        scene.add(particle);
        particles.push({
            mesh: particle,
            theta: theta,
            speed: 0.001 + Math.random() * 0.002
        });
    }
    
    // Свет
    const light1 = new THREE.PointLight(0xff3366, 1);
    light1.position.set(2, 2, 3);
    scene.add(light1);
    
    const light2 = new THREE.PointLight(0x33ff66, 0.8);
    light2.position.set(-2, 1, 4);
    scene.add(light2);
    
    const ambient = new THREE.AmbientLight(0x333333);
    scene.add(ambient);
    
    function animate() {
        requestAnimationFrame(animate);
        
        torus.rotation.x += 0.01;
        torus.rotation.y += 0.015;
        
        particles.forEach(p => {
            p.theta += p.speed;
            const x = 2.5 * Math.sin(p.theta) * Math.cos(p.theta);
            const y = 2.5 * Math.sin(p.theta) * Math.sin(p.theta);
            const z = 2.5 * Math.cos(p.theta);
            p.mesh.position.set(x, y, z);
        });
        
        if (window.scrollProgress !== undefined) {
            const progress = Math.min(window.scrollProgress, 1);
            camera.position.z = 5 + progress * 4;
            torus.material.emissiveIntensity = 1 - progress;
        }
        
        renderer.render(scene, camera);
    }
    
    animate();
    
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
    
    console.log('Three.js ready');
});
