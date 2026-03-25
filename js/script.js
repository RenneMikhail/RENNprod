document.addEventListener('DOMContentLoaded', () => {
    const heroText = document.querySelector('.hero-title');
    const contentWrapper = document.getElementById('contentWrapper');
    const bgVideo = document.getElementById('bgVideo');
    
    // Массив видео для фона (если нужно переключать)
    const videos = ['video/1.mp4', 'video/2.mp4', 'video/3.mp4', 'video/4.mp4', 'video/5.mp4'];
    let currentVideo = 0;
    
    function updateHeroAnimation() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const progress = Math.min(scrollY / windowHeight, 1);
        
        // Передаем прогресс в Three.js
        window.scrollProgress = progress;
        
        // Анимация текста
        if (heroText) {
            const startSize = 8;
            const endSize = 2;
            let currentSize = startSize - (progress * (startSize - endSize));
            currentSize = Math.max(endSize, currentSize);
            heroText.style.fontSize = `${currentSize}vw`;
            heroText.style.opacity = 1 - progress;
            heroText.style.transform = `translateY(${progress * -80}px)`;
        }
        
        // Эффект для видео фона
        if (bgVideo) {
            bgVideo.style.opacity = 0.6 - progress * 0.4;
            bgVideo.style.transform = `scale(${1 + progress * 0.1})`;
        }
    }
    
    window.addEventListener('scroll', updateHeroAnimation);
    updateHeroAnimation();
    
    // Опционально: смена видео при скролле
    // Можно раскомментировать если нужно переключать видео
    /*
    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const videoIndex = Math.floor(scrollY / windowHeight);
        
        if (videoIndex !== currentVideo && videoIndex < videos.length && bgVideo) {
            currentVideo = videoIndex;
            bgVideo.src = videos[currentVideo];
            bgVideo.load();
            bgVideo.play();
        }
    });
    */
});
