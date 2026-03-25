document.addEventListener('DOMContentLoaded', () => {
    const heroTitle = document.querySelector('.hero-title');
    const bgVideo = document.getElementById('bgVideo');
    const modelViewer = document.getElementById('scrollingModel');
    const modelSection = document.getElementById('modelShowcase');
    
    function updateAnimation() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const progress = Math.min(scrollY / windowHeight, 1);
        
        window.scrollProgress = progress;
        
        // Анимация текста RENNprod
        if (heroTitle) {
            const startSize = 12;
            const endSize = 2;
            let currentSize = startSize - (progress * (startSize - endSize));
            currentSize = Math.max(endSize, currentSize);
            heroTitle.style.fontSize = `${currentSize}vw`;
            
            const startTop = 15;
            const endTop = -30;
            let currentTop = startTop - (progress * (startTop - endTop));
            heroTitle.style.top = `${currentTop}vh`;
            
            heroTitle.style.opacity = 1 - progress;
            
            const scaleY = 1 + (progress * 1.5);
            heroTitle.style.transform = `scaleY(${scaleY})`;
            heroTitle.style.transformOrigin = "top center";
        }
        
        // Анимация модели во втором блоке
        if (modelViewer && modelSection) {
            const sectionTop = modelSection.offsetTop;
            const sectionHeight = modelSection.offsetHeight;
            const scrollPosition = scrollY + windowHeight;
            
            // Когда пользователь прокручивает блок с моделью
            let modelProgress = 0;
            if (scrollY + windowHeight > sectionTop && scrollY < sectionTop + sectionHeight) {
                // Вычисляем прогресс внутри блока (0 = начало блока, 1 = конец блока)
                const scrollInSection = scrollY - sectionTop;
                modelProgress = Math.min(Math.max(scrollInSection / sectionHeight, 0), 1);
                
                // Растягиваем модель при скролле внутри блока
                const scaleStretch = 1 + (modelProgress * 0.8);
                modelViewer.style.transform = `scaleY(${scaleStretch})`;
                modelViewer.style.transformOrigin = "center center";
                
                // Увеличиваем скорость вращения при скролле
                const rotationSpeed = 20 + (modelProgress * 30);
                modelViewer.setAttribute('rotation-per-second', `${rotationSpeed}deg`);
            } else {
                modelViewer.style.transform = `scaleY(1)`;
                modelViewer.setAttribute('rotation-per-second', `20deg`);
            }
        }
        
        if (bgVideo) {
            bgVideo.style.opacity = 0.6 - progress * 0.4;
        }
    }
    
    // Обновляем при скролле
    window.addEventListener('scroll', updateAnimation);
    updateAnimation();
    
    // Обновляем при изменении размера окна (для пересчета позиций)
    window.addEventListener('resize', () => {
        updateAnimation();
    });
});