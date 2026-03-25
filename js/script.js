document.addEventListener('DOMContentLoaded', () => {
    const heroText = document.querySelector('.hero-title');
    
    function updateHeroAnimation() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const progress = Math.min(scrollY / windowHeight, 1);
        
        window.scrollProgress = progress;
        
        if (heroText) {
            const startSize = 8;
            const endSize = 2;
            let currentSize = startSize - (progress * (startSize - endSize));
            currentSize = Math.max(endSize, currentSize);
            heroText.style.fontSize = `${currentSize}vw`;
            heroText.style.opacity = 1 - progress;
            heroText.style.transform = `translateY(${progress * -50}px)`;
        }
    }
    
    window.addEventListener('scroll', updateHeroAnimation);
    updateHeroAnimation();
});
