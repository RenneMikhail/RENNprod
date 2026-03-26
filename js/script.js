document.addEventListener('DOMContentLoaded', () => {
    const heroTitle = document.querySelector('.hero-title');
    const bgVideo = document.getElementById('bgVideo');
    let ticking = false;
    let currentProgress = 0;
    
    function updateAnimation() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const progress = Math.min(scrollY / windowHeight, 1);
        
        currentProgress = progress;
        window.scrollProgress = progress;
        
        if (heroTitle) {
            // Плавное уменьшение шрифта
            const startSize = 12;
            const endSize = 2;
            let currentSize = startSize - (progress * (startSize - endSize));
            currentSize = Math.max(endSize, currentSize);
            heroTitle.style.fontSize = `${currentSize}vw`;
            
            // Плавное смещение вверх
            const startTop = 15;
            const endTop = -30;
            let currentTop = startTop - (progress * (startTop - endTop));
            heroTitle.style.top = `${currentTop}vh`;
            
            // Плавное изменение прозрачности
            heroTitle.style.opacity = 1 - progress;
            
            // Плавное растяжение
            const scaleY = 1 + (progress * 1.5);
            heroTitle.style.transform = `scaleY(${scaleY})`;
            heroTitle.style.transformOrigin = "top center";
        }
        
        if (bgVideo) {
            bgVideo.style.opacity = 0.6 - progress * 0.4;
        }
    }
    
    // Оптимизация с requestAnimationFrame для плавности
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                updateAnimation();
                ticking = false;
            });
            ticking = true;
        }
    });
    
    // Запускаем один раз для начального состояния
    updateAnimation();
});