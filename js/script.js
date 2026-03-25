// Анимация растяжения текста при скролле
function updateTextStretch() {
    const textEl = document.getElementById('animatedText');
    if (!textEl) return;
    
    const heroBlock = document.querySelector('.hero');
    if (!heroBlock) return;
    
    const rect = heroBlock.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    
    let progress = 0;
    
    // Прогресс от 0 до 1 при любом движении скролла вниз
    if (rect.bottom <= 0) {
        progress = 1;
    } else if (rect.top >= windowHeight) {
        progress = 0;
    } else if (rect.top <= 0 && rect.bottom > 0) {
        progress = Math.min(1, 1 - (rect.bottom / windowHeight));
    } else if (rect.top > 0) {
        progress = Math.min(1, rect.top / windowHeight);
    }
    
    // Растяжение: от 1 (норма) до 10 (максимум)
    const stretch = 1 + (progress * 9);
    textEl.style.transform = `scaleY(${stretch})`;
    textEl.style.transformOrigin = "center bottom";
}

window.addEventListener('scroll', updateTextStretch);
window.addEventListener('resize', updateTextStretch);
document.addEventListener('DOMContentLoaded', updateTextStretch);
