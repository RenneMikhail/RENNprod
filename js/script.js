document.addEventListener('DOMContentLoaded', () => {
    const hero = document.getElementById('hero');
    const heroText = document.getElementById('heroText');
    const contentWrapper = document.getElementById('contentWrapper');

    // Функция для обновления анимации при скролле
    function updateHeroAnimation() {
        // Получаем позицию скролла
        const scrollY = window.scrollY;
        // Высота окна
        const windowHeight = window.innerHeight;
        
        // Прогресс скролла в пределах первого экрана (от 0 до 1)
        // Когда скролл = 0 -> progress = 0, когда скролл = windowHeight -> progress = 1
        let progress = Math.min(scrollY / windowHeight, 1);
        
        // 1. Анимация текста: размер от 15vw до 3vw
        // Начальный размер (15vw) указан в CSS, конечный (3vw) будем применять через inline style
        const startSize = 15; // vw
        const endSize = 3;    // vw
        let currentSize = startSize - (progress * (startSize - endSize));
        // Ограничиваем, чтобы не стал меньше конечного
        currentSize = Math.max(endSize, currentSize);
        
        // Применяем размер шрифта (в vw)
        heroText.style.fontSize = `${currentSize}vw`;
        
        // 2. Прозрачность hero-блока: исчезает к концу скролла первого экрана
        hero.style.opacity = 1 - progress;
        
        // 3. Трансформация: небольшой сдвиг вверх для эффекта "уезжания"
        hero.style.transform = `translateY(${progress * -50}px)`;
        
        // 4. Фиксация позиции hero: когда прогресс = 1, делаем его position: absolute,
        // чтобы он не перекрывал контент (но с opacity=0 это не критично)
        if (progress >= 0.99) {
            hero.style.position = 'absolute';
            hero.style.top = '0';
        } else {
            hero.style.position = 'fixed';
        }
    }
    
    // Вызываем при скролле
    window.addEventListener('scroll', updateHeroAnimation);
    // Вызываем один раз для установки начальных значений
    updateHeroAnimation();
});