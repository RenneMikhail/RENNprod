document.addEventListener('DOMContentLoaded', () => {
    const heroTitle = document.querySelector('.hero-title');
    const contentWrapper = document.getElementById('contentWrapper');
    const bgVideo = document.getElementById('bgVideo');
    
    function updateAnimation() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const progress = Math.min(scrollY / windowHeight, 1);
        
        window.scrollProgress = progress;
        
        if (heroTitle) {
            // 1. Шрифт уменьшается от 12vw до 2vw
            const startSize = 12;
            const endSize = 2;
            let currentSize = startSize - (progress * (startSize - endSize));
            currentSize = Math.max(endSize, currentSize);
            heroTitle.style.fontSize = `${currentSize}vw`;
            
            // 2. Текст смещается вверх (начальная позиция - верх экрана)
            // При progress=0: top = 15vh, при progress=1: top = -20vh (уезжает)
            const startTop = 15; // % от высоты экрана
            const endTop = -30;   // % (уходит вверх)
            let currentTop = startTop - (progress * (startTop - endTop));
            heroTitle.style.top = `${currentTop}vh`;
            
            // 3. Прозрачность
            heroTitle.style.opacity = 1 - progress;
            
            // 4. Растяжение по вертикали (scaleY)
            // При progress=0: scaleY=1, при progress=1: scaleY=2.5
            const scaleY = 1 + (progress * 1.5);
            heroTitle.style.transform = `scaleY(${scaleY})`;
            heroTitle.style.transformOrigin = "top center";
        }
        
        if (bgVideo) {
            bgVideo.style.opacity = 0.6 - progress * 0.4;
        }
    }
    
    window.addEventListener('scroll', updateAnimation);
    updateAnimation();
});
