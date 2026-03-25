import * as THREE from 'three';

// Инициализация сцены
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x000000); // Черный фон

// Камера (перспективная)
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0, 5);
camera.lookAt(0, 0, 0);

// Рендерер с прозрачностью (чтобы смешивать с текстом)
const canvas = document.getElementById('bgCanvas');
const renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);

// --- Создаем красивый объект ---

// 1. Основной тор (похож на Zebra Hero)
const geometry = new THREE.TorusGeometry(1.2, 0.25, 64, 200);
const material = new THREE.MeshStandardMaterial({
    color: 0xff3366,
    emissive: 0x441122,
    metalness: 0.8,
    roughness: 0.2,
    wireframe: false
});
const torus = new THREE.Mesh(geometry, material);
scene.add(torus);

// 2. Добавляем вращающиеся маленькие сферы вокруг
const particleCount = 200;
const particles = [];
const particleGeometry = new THREE.SphereGeometry(0.03, 8, 8);

for (let i = 0; i < particleCount; i++) {
    const particleMaterial = new THREE.MeshStandardMaterial({
        color: 0xff6699,
        emissive: 0x331122
    });
    const particle = new THREE.Mesh(particleGeometry, particleMaterial);
    
    // Случайное положение на сфере радиуса 2.5
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

// 3. Добавляем подсветку
const ambientLight = new THREE.AmbientLight(0x333333);
scene.add(ambientLight);

const pointLight = new THREE.PointLight(0xff6699, 1);
pointLight.position.set(2, 3, 4);
scene.add(pointLight);

const pointLight2 = new THREE.PointLight(0x3399ff, 0.8);
pointLight2.position.set(-2, 1, 3);
scene.add(pointLight2);

const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
directionalLight.position.set(1, 2, 1);
scene.add(directionalLight);

// Переменные для анимации скролла
let scrollProgress = 0; // 0 = начало, 1 = конец первого экрана

// Анимация
function animate() {
    requestAnimationFrame(animate);
    
    // Вращение основного тора
    torus.rotation.x += 0.008;
    torus.rotation.y += 0.012;
    torus.rotation.z += 0.005;
    
    // Анимация частиц — они вращаются вокруг центра
    particles.forEach(particle => {
        particle.theta += particle.speed;
        const x = particle.radius * Math.sin(particle.theta) * Math.cos(particle.phi);
        const y = particle.radius * Math.sin(particle.theta) * Math.sin(particle.phi);
        const z = particle.radius * Math.cos(particle.theta);
        particle.mesh.position.set(x, y, z);
    });
    
    // Реакция на скролл: камера отъезжает назад, объект становится меньше
    // scrollProgress приходит из основного script.js через глобальную переменную
    if (window.scrollProgress !== undefined) {
        const progress = window.scrollProgress;
        // Камера отъезжает от 5 до 8
        camera.position.z = 5 + progress * 3;
        // Объект становится менее ярким
        torus.material.emissiveIntensity = 1 - progress;
        torus.material.opacity = 1 - progress;
        torus.material.transparent = true;
    }
    
    renderer.render(scene, camera);
}

animate();

// Обработка изменения размера окна
window.addEventListener('resize', onWindowResize, false);
function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}
