// Анимация растяжения и исчезновения текста при скролле
function updateTextStretch() {
    const textEl = document.getElementById('animatedText');
    if (!textEl) return;
    
    const heroBlock = document.querySelector('.hero');
    if (!heroBlock) return;
    
    const rect = heroBlock.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    
    let progress = 0;
    
    // Вычисляем прогресс скролла (0 = блок полностью виден, 1 = блок полностью скрыт)
    if (rect.bottom <= 0) {
        progress = 1;
    } else if (rect.top >= windowHeight) {
        progress = 0;
    } else if (rect.top <= 0 && rect.bottom > 0) {
        progress = Math.min(1, 1 - (rect.bottom / windowHeight));
    } else if (rect.top > 0) {
        progress = Math.min(1, rect.top / windowHeight);
    }
    
    // Растяжение: максимальное 3.5 (в 3.5 раза выше) при progress = 0
    const stretch = 1 + ((1 - progress) * 2.5);
    textEl.style.transform = `scaleY(${stretch})`;
    
    // Межбуквенное расстояние: максимальное 25px при progress = 0
    const letterSpacing = Math.floor((1 - progress) * 25);
    textEl.style.letterSpacing = `${letterSpacing}px`;
    
    // Прозрачность: исчезает при скролле
    const opacity = 1 - progress;
    textEl.style.opacity = opacity;
}

// Запускаем функцию
window.addEventListener('scroll', updateTextStretch);
window.addEventListener('resize', updateTextStretch);
document.addEventListener('DOMContentLoaded', updateTextStretch);
