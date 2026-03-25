import * as THREE from 'three';

// Инициализация
const canvas = document.getElementById('bgCanvas');
if (!canvas) {
    console.error('Canvas not found!');
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x000000);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0, 5);

const renderer = new THREE.WebGLRenderer({ canvas, alpha: false });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);

// Создаем красивый объект (тор)
const geometry = new THREE.TorusGeometry(1.2, 0.25, 64, 200);
const material = new THREE.MeshStandardMaterial({
    color: 0xff3366,
    emissive: 0x441122,
    metalness: 0.8,
    roughness: 0.2
});
const torus = new THREE.Mesh(geometry, material);
scene.add(torus);

// Частицы вокруг
const particleCount = 200;
const particles = [];

for (let i = 0; i < particleCount; i++) {
    const particleGeometry = new THREE.SphereGeometry(0.03, 8, 8);
    const particleMaterial = new THREE.MeshStandardMaterial({ color: 0xff6699 });
    const particle = new THREE.Mesh(particleGeometry, particleMaterial);
    
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const radius = 2.2;
    particle.position.x = radius * Math.sin(phi) * Math.cos(theta);
    particle.position.y = radius * Math.sin(phi) * Math.sin(theta);
    particle.position.z = radius * Math.cos(phi);
    
    scene.add(particle);
    particles.push({
        mesh: particle,
        theta: theta,
        phi: phi,
        radius: radius,
        speed: 0.002 + Math.random() * 0.003
    });
}

// Освещение
const ambientLight = new THREE.AmbientLight(0x333333);
scene.add(ambientLight);

const pointLight = new THREE.PointLight(0xff6699, 1);
pointLight.position.set(2, 3, 4);
scene.add(pointLight);

const pointLight2 = new THREE.PointLight(0x3399ff, 0.8);
pointLight2.position.set(-2, 1, 3);
scene.add(pointLight2);

// Анимация
function animate() {
    requestAnimationFrame(animate);
    
    torus.rotation.x += 0.008;
    torus.rotation.y += 0.012;
    
    particles.forEach(particle => {
        particle.theta += particle.speed;
        const x = particle.radius * Math.sin(particle.theta) * Math.cos(particle.phi);
        const y = particle.radius * Math.sin(particle.theta) * Math.sin(particle.phi);
        const z = particle.radius * Math.cos(particle.theta);
        particle.mesh.position.set(x, y, z);
    });
    
    // Реакция на скролл
    if (window.scrollProgress !== undefined) {
        camera.position.z = 5 + window.scrollProgress * 3;
        torus.material.emissiveIntensity = 1 - window.scrollProgress;
    }
    
    renderer.render(scene, camera);
}

animate();

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

console.log('Three.js initialized successfully');
