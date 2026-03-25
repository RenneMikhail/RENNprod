import * as THREE from 'three';
import { GLTFLoader } from 'https://unpkg.com/three@0.128.0/examples/jsm/loaders/GLTFLoader.js';

// Ждем полной загрузки страницы
window.addEventListener('load', () => {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) {
        console.error('Canvas element not found!');
        return;
    }

    // 1. СОЗДАЕМ СЦЕНУ
    const scene = new THREE.Scene();
    scene.background = null; // Прозрачный фон, чтобы видео было видно
    
    // 2. КАМЕРА
    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 0.5, 4);
    camera.lookAt(0, 0, 0);
    
    // 3. РЕНДЕРЕР
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(window.devicePixelRatio);
    
    // 4. ОСВЕЩЕНИЕ (чтобы модель была видна)
    // Окружающий свет
    const ambientLight = new THREE.AmbientLight(0x404060);
    scene.add(ambientLight);
    
    // Основной направленный свет
    const mainLight = new THREE.DirectionalLight(0xffffff, 1.2);
    mainLight.position.set(2, 3, 4);
    scene.add(mainLight);
    
    // Задний контровой свет (розовый)
    const backLight = new THREE.PointLight(0xff3366, 0.8);
    backLight.position.set(-1, 1, -2);
    scene.add(backLight);
    
    // Заполняющий свет (голубой)
    const fillLight = new THREE.PointLight(0x3366ff, 0.5);
    fillLight.position.set(1, 0.5, 2);
    scene.add(fillLight);
    
    // Верхний свет
    const topLight = new THREE.PointLight(0xffaa66, 0.6);
    topLight.position.set(0, 2, 0);
    scene.add(topLight);
    
    let model = null;
    
    // 5. ЗАГРУЗКА МОДЕЛИ
    const loader = new GLTFLoader();
    loader.load(
        'models/22.gltf',
        (gltf) => {
            model = gltf.scene;
            // Настройка позиции и размера модели
            model.scale.set(1.2, 1.2, 1.2);
            model.position.set(0, -0.3, 0);
            model.rotation.y = 0;
            scene.add(model);
            console.log('✅ Модель 22.gltf загружена и добавлена в сцену!');
        },
        (xhr) => {
            console.log(`Загрузка модели: ${Math.round(xhr.loaded / xhr.total * 100)}%`);
        },
        (error) => {
            console.error('❌ Ошибка загрузки модели:', error);
            // Если модель не загрузилась, создаем красивый объект
            const geometry = new THREE.TorusKnotGeometry(0.8, 0.2, 100, 16);
            const material = new THREE.MeshStandardMaterial({
                color: 0xff3366,
                emissive: 0x441122,
                metalness: 0.8,
                roughness: 0.2
            });
            model = new THREE.Mesh(geometry, material);
            model.position.set(0, 0, 0);
            scene.add(model);
            console.log('⚠️ Используется запасной 3D объект');
        }
    );
    
    // 6. АНИМАЦИЯ
    function animate() {
        requestAnimationFrame(animate);
        
        if (model) {
            model.rotation.y += 0.01;
            model.rotation.x += 0.005;
        }
        
        // Реакция на скролл
        if (window.scrollProgress !== undefined) {
            const progress = Math.min(window.scrollProgress, 1);
            camera.position.z = 4 + progress * 3;
            if (model && model.material) {
                model.material.emissiveIntensity = 1 - progress;
            }
        }
        
        renderer.render(scene, camera);
    }
    
    animate();
    
    // 7. АДАПТАЦИЯ ПОД РАЗМЕР ОКНА
    window.addEventListener('resize', onWindowResize, false);
    function onWindowResize() {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }
    
    console.log('Three.js сцена запущена, ожидаем модель');
});
