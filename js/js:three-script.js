import * as THREE from 'three';
import { GLTFLoader } from 'https://unpkg.com/three@0.128.0/examples/jsm/loaders/GLTFLoader.js';

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) {
        console.error('Canvas not found');
        return;
    }

    // СЦЕНА
    const scene = new THREE.Scene();
    scene.background = null; // Прозрачный фон, чтобы видео было видно
    
    // КАМЕРА
    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 1, 5);
    camera.lookAt(0, 0, 0);
    
    // РЕНДЕРЕР
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    
    // ОСВЕЩЕНИЕ
    const ambientLight = new THREE.AmbientLight(0x404060);
    scene.add(ambientLight);
    
    const mainLight = new THREE.DirectionalLight(0xffffff, 1.2);
    mainLight.position.set(2, 3, 4);
    scene.add(mainLight);
    
    const backLight = new THREE.PointLight(0xff3366, 0.8);
    backLight.position.set(-1, 1, -2);
    scene.add(backLight);
    
    const fillLight = new THREE.PointLight(0x3366ff, 0.5);
    fillLight.position.set(1, 0.5, 2);
    scene.add(fillLight);
    
    const rimLight = new THREE.PointLight(0xffaa66, 0.6);
    rimLight.position.set(0, 1.5, -2.5);
    scene.add(rimLight);
    
    let model = null;
    
    // ЗАГРУЗКА МОДЕЛИ
    const loader = new GLTFLoader();
    loader.load(
        'models/22.gltf',
        (gltf) => {
            model = gltf.scene;
            // Настройка размера и позиции модели
            model.scale.set(1.2, 1.2, 1.2);
            model.position.set(0, -0.5, 0);
            model.rotation.y = 0;
            scene.add(model);
            console.log('✅ Модель 22.gltf успешно загружена!');
        },
        (xhr) => {
            console.log(`Загрузка модели: ${Math.round(xhr.loaded / xhr.total * 100)}%`);
        },
        (error) => {
            console.error('❌ Ошибка загрузки модели:', error);
            // Создаем запасной объект, если модель не загрузилась
            const geometry = new THREE.TorusGeometry(1.2, 0.25, 64, 200);
            const material = new THREE.MeshStandardMaterial({
                color: 0xff3366,
                emissive: 0x441122,
                metalness: 0.9,
                roughness: 0.2
            });
            model = new THREE.Mesh(geometry, material);
            scene.add(model);
            console.log('⚠️ Используется запасной объект (тор)');
        }
    );
    
    // АНИМАЦИЯ
    function animate() {
        requestAnimationFrame(animate);
        
        if (model) {
            model.rotation.y += 0.008;
            model.rotation.x += 0.003;
        }
        
        // Реакция на скролл
        if (window.scrollProgress !== undefined) {
            const progress = Math.min(window.scrollProgress, 1);
            camera.position.z = 5 + progress * 4;
            if (model && model.material) {
                model.material.emissiveIntensity = 1 - progress;
            }
        }
        
        renderer.render(scene, camera);
    }
    
    animate();
    
    // АДАПТАЦИЯ ПОД РАЗМЕР ЭКРАНА
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
    
    console.log('Three.js инициализирован, ждем загрузку модели');
});
