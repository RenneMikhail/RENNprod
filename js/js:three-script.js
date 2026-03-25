import * as THREE from 'three';

// Ждем загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) {
        console.error('Canvas not found!');
        return;
    }

    // Сцена
    const scene = new THREE.Scene();
    scene.background = null; // Прозрачный фон, чтобы видео было видно
    
    // Камера
    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 0, 5);
    
    // Рендерер с прозрачностью
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0); // Прозрачный фон
    
    // Создаем эффектный 3D объект (тор)
    const geometry = new THREE.TorusGeometry(1.3, 0.25, 64, 200);
    const material = new THREE.MeshStandardMaterial({
        color: 0xff3366,
        emissive: 0x441122,
        metalness: 0.9,
        roughness: 0.1,
        transparent: true,
        opacity: 0.95
    });
    const torus = new THREE.Mesh(geometry, material);
    scene.add(torus);
    
    // Добавляем вращающиеся частицы
    const particleCount = 300;
    const particles = [];
    const particleGeometry = new THREE.SphereGeometry(0.04, 8, 8);
    
    for (let i = 0; i < particleCount; i++) {
        const particleMaterial = new THREE.MeshStandardMaterial({
            color: 0xff6699,
            emissive: 0x331122
        });
        const particle = new THREE.Mesh(particleGeometry, particleMaterial);
        
        // Случайное распределение на сфере
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
            phi: phi,
            radius: radius,
            speed: 0.001 + Math.random() * 0.002
        });
    }
    
    // Освещение
    const ambientLight = new THREE.AmbientLight(0x333333);
    scene.add(ambientLight);
    
    const pointLight1 = new THREE.PointLight(0xff3366, 1);
    pointLight1.position.set(2, 2, 3);
    scene.add(pointLight1);
    
    const pointLight2 = new THREE.PointLight(0x33ff66, 0.8);
    pointLight2.position.set(-2, 1, 4);
    scene.add(pointLight2);
    
    const pointLight3 = new THREE.PointLight(0x3366ff, 0.6);
    pointLight3.position.set(0, -2, 3);
    scene.add(pointLight3);
    
    // Анимация
    function animate() {
        requestAnimationFrame(animate);
        
        // Вращение тора
        torus.rotation.x += 0.01;
        torus.rotation.y += 0.015;
        torus.rotation.z += 0.005;
        
        // Анимация частиц
        particles.forEach(particle => {
            particle.theta += particle.speed;
            const x = particle.radius * Math.sin(particle.theta) * Math.cos(particle.phi);
            const y = particle.radius * Math.sin(particle.theta) * Math.sin(particle.phi);
            const z = particle.radius * Math.cos(particle.theta);
            particle.mesh.position.set(x, y, z);
        });
        
        // Реакция на скролл
        if (window.scrollProgress !== undefined) {
            const progress = Math.min(window.scrollProgress, 1);
            camera.position.z = 5 + progress * 4;
            torus.material.emissiveIntensity = 1 - progress;
            torus.material.opacity = 0.95 - progress * 0.7;
            
            // Частицы улетают
            particles.forEach((particle, idx) => {
                const scale = 1 - progress * 0.5;
                particle.mesh.scale.set(scale, scale, scale);
            });
        }
        
        renderer.render(scene, camera);
    }
    
    animate();
    
    // Адаптация к размеру окна
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
    
    console.log('Three.js initialized with video background');
});
