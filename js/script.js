// js/script.js
// Анимация растяжения текста при скролле

function updateTextStretch() {
    const textEl = document.getElementById('animatedText');
    if (!textEl) return;
    
    // Находим родительский блок hero
    const heroBlock = document.querySelector('.hero');
    if (!heroBlock) return;
    
    // Получаем позицию блока hero относительно окна браузера
    const rect = heroBlock.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    
    // Вычисляем, насколько блок hero виден на экране
    let progress = 0;
    
    // Когда блок полностью в поле зрения
    if (rect.top <= 0 && rect.bottom >= windowHeight) {
        progress = 1;
    }
    // Когда блок частично виден сверху или снизу
    else if (rect.top <= 0 && rect.bottom > 0) {
        // Выходит за верхний край
        progress = Math.min(1, rect.bottom / windowHeight);
    }
    else if (rect.top > 0 && rect.top < windowHeight) {
        // Входит снизу
        progress = 1 - (rect.top / windowHeight);
    }
    
    // Применяем эффект растяжения по вертикали (scaleY)
    // Максимальное растяжение в 2.2 раза при progress = 1
    const stretch = 1 + (progress * 1.2);
    textEl.style.transform = `scaleY(${stretch})`;
    
    // Динамическое межбуквенное расстояние
    const letterSpacing = Math.floor(progress * 12);
    textEl.style.letterSpacing = `${letterSpacing}px`;
}

// Запускаем функцию при скролле и при загрузке страницы
window.addEventListener('scroll', updateTextStretch);
window.addEventListener('resize', updateTextStretch);
document.addEventListener('DOMContentLoaded', updateTextStretch);