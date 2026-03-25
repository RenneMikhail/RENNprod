import * as THREE from 'three';
import { GLTFLoader } from 'https://unpkg.com/three@0.128.0/examples/jsm/loaders/GLTFLoader.js';

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) {
        console.error('Canvas not found');
        return;
    }

    const scene = new THREE.Scene();
    scene.background = null;
    
    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 1, 5);
    
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    
    // Освещение для модели
    const ambientLight = new THREE.AmbientLight(0x404040);
    scene.add(ambientLight);
    
    const mainLight = new THREE.DirectionalLight(0xffffff, 1);
    mainLight.position.set(2, 3, 4);
    scene.add(mainLight);
    
    const backLight = new THREE.PointLight(0xff3366, 0.5);
    backLight.position.set(-1, 1, -2);
    scene.add(backLight);
    
    const fillLight = new THREE.PointLight(0x3366ff, 0.3);
    fillLight.position.set(1, 0, 2);
    scene.add(fillLight);
    
    let model = null;
    
    // ЗАГРУЗКА GLTF МОДЕЛИ
    const loader = new GLTFLoader();
    loader.load(
        'models/your-model.glb',  // <-- ЗДЕСЬ ИМЯ ТВОЕГО ФАЙЛА
        (gltf) => {
            model = gltf.scene;
            model.scale.set(1, 1, 1);
            model.position.set(0, 0, 0);
            scene.add(model);
            console.log('Model loaded successfully');
        },
        (xhr) => {
            console.log((xhr.loaded / xhr.total * 100) + '% loaded');
        },
        (error) => {
            console.error('Error loading model:', error);
            // Если модели нет, создаем запасной объект
            createFallbackObject(scene);
        }
    );
    
    // Запасной объект, если модель не загрузилась
    function createFallbackObject(scene) {
        const geometry = new THREE.TorusGeometry(1.2, 0.25, 64, 200);
        const material = new THREE.MeshStandardMaterial({
            color: 0xff3366,
            emissive: 0x441122,
            metalness: 0.9,
            roughness: 0.1
        });
        const fallback = new THREE.Mesh(geometry, material);
        scene.add(fallback);
        model = fallback;
    }
    
    function animate() {
        requestAnimationFrame(animate);
        
        if (model) {
            model.rotation.y += 0.01;
            model.rotation.x += 0.005;
        }
        
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
    
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
});
