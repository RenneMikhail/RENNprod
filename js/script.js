// Анимация растяжения текста при скролле (эффект жевачки)
function updateTextStretch() {
    const textEl = document.getElementById('animatedText');
    if (!textEl) return;
    
    const heroBlock = document.querySelector('.hero');
    if (!heroBlock) return;
    
    const rect = heroBlock.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    
    let progress = 0;
    
    // Вычисляем прогресс скролла: 0 = блок полностью виден, 1 = блок полностью скрыт
    if (rect.bottom <= 0) {
        progress = 1;
    } else if (rect.top >= windowHeight) {
        progress = 0;
    } else if (rect.top <= 0 && rect.bottom > 0) {
        progress = Math.min(1, 1 - (rect.bottom / windowHeight));
    } else if (rect.top > 0) {
        progress = Math.min(1, rect.top / windowHeight);
    }
    
    // Растяжение по Y: от 1 (норма) до 2.8 (максимум)
    const stretch = 1 + (progress * 1.8);
    textEl.style.transform = `scaleY(${stretch})`;
    textEl.style.transformOrigin = "center bottom";
    
    // Сохраняем цвет белым
    textEl.style.color = "#FFFFFF";
}

window.addEventListener('scroll', updateTextStretch);
window.addEventListener('resize', updateTextStretch);
document.addEventListener('DOMContentLoaded', updateTextStretch);
