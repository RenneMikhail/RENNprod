document.addEventListener('DOMContentLoaded', () => {
    const heroText = document.querySelector('.hero-title');
    const contentWrapper = document.getElementById('contentWrapper');
    
    // Функция для обновления анимации текста и передачи прогресса в Three.js
    function updateHeroAnimation() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        
        let progress = Math.min(scrollY / windowHeight, 1);
        
        // Передаем прогресс в Three.js сцену через глобальную переменную
        window.scrollProgress = progress;
        
        // Анимация текста: уменьшается и исчезает
        if (heroText) {
            const startSize = 8; // vw
            const endSize = 2;    // vw
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
