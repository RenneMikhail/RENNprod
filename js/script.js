document.addEventListener('DOMContentLoaded', () => {
    const heroTitle = document.querySelector('.hero-title');
    const bgVideo = document.getElementById('bgVideo');
    
    function updateAnimation() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const progress = Math.min(scrollY / windowHeight, 1);
        
        window.scrollProgress = progress;
        
        if (heroTitle) {
            const fontSize = 8 - (progress * 6);
            heroTitle.style.fontSize = `${Math.max(2, fontSize)}vw`;
            heroTitle.style.opacity = 1 - progress;
            heroTitle.style.transform = `translateY(${progress * -80}px)`;
        }
        
        if (bgVideo) {
            bgVideo.style.opacity = 0.6 - progress * 0.4;
        }
    }
    
    window.addEventListener('scroll', updateAnimation);
    updateAnimation();
});
