document.addEventListener('DOMContentLoaded', () => {
    
    const themeSelect = document.getElementById('theme-select');
 
    const initialTheme = document.documentElement.getAttribute('data-theme') || 'tokyo-night';

 
    const updateColorPaletteDisplay = () => {
        const colorPaletteDisplay = document.getElementById('color-palette-display');
        if (!colorPaletteDisplay) return;

     
        colorPaletteDisplay.innerHTML = '';

        const rootStyles = getComputedStyle(document.documentElement);
        const colors = ['--primary', '--secondary', '--accent', '--bg', '--fg', '--surface'];

        colors.forEach(colorVar => {
            const colorValue = rootStyles.getPropertyValue(colorVar).trim();
            if (colorValue) {
                const swatch = document.createElement('div');
                swatch.className = 'color-swatch';
                swatch.style.backgroundColor = colorValue;
                swatch.title = `${colorVar}: ${colorValue}`;
                colorPaletteDisplay.appendChild(swatch);
            }
        });
    };


    const themeDisplay = document.getElementById('theme-display');
    const themePrev = document.getElementById('theme-prev');
    const themeNext = document.getElementById('theme-next');
    const themes = [
        {value: 'tokyo-night', label: 'Tokyo Night'},
        {value: 'rose-pine', label: 'Rosé Pine'},
        {value: 'catppuccin-mocha', label: 'Catppuccin Mocha'},
        {value: 'catppuccin-macchiato', label: 'Catppuccin Macchiato'},
        {value: 'catppuccin-frappe', label: 'Catppuccin Frappe'},
        {value: 'catppuccin-latte', label: 'Catppuccin Latte'},
        {value: 'nord', label: 'Nord'},
        {value: 'gruvbox-dark', label: 'Gruvbox Dark'},
        {value: 'gruvbox-light', label: 'Gruvbox Light'},
        {value: 'dracula', label: 'Dracula'},
        {value: 'monokai-pro', label: 'Monokai Pro'},
        {value: 'solarized-light', label: 'Solarized Light'},
        {value: 'solarized-dark', label: 'Solarized Dark'},
        {value: 'one-dark-pro', label: 'One Dark Pro'},
        {value: 'ayu-dark', label: 'Ayu Dark'}
    ];

 
    const stored = localStorage.getItem('selectedTheme') || document.documentElement.getAttribute('data-theme') || 'tokyo-night';
    let currentIndex = themes.findIndex(t => t.value === stored);
    if (currentIndex === -1) currentIndex = 0;


    function animateThemeChange(newLabel, direction) {
        if (!themeDisplay) return;

        const incoming = document.createElement('span');
        incoming.className = 'theme-label incoming';
        incoming.textContent = newLabel;

        if (direction === 'next') {
            incoming.classList.add('enter-from-right');
        } else {
            incoming.classList.add('enter-from-left');
        }

        themeDisplay.appendChild(incoming);


        void incoming.offsetWidth;


        incoming.classList.add('enter-to');
        
        const outgoing = themeDisplay.querySelector('.theme-label:not(.incoming)');
        if (outgoing) {
            if (direction === 'next') {
                outgoing.classList.add('exit-to-left');
            } else {
                outgoing.classList.add('exit-to-right');
            }
            outgoing.addEventListener('transitionend', () => {
                outgoing.remove();
            }, { once: true });
        }

        incoming.addEventListener('transitionend', () => {
            incoming.classList.remove('incoming', 'enter-from-right', 'enter-from-left', 'enter-to');
            incoming.classList.add('theme-label');
        }, { once: true });
    }

    function applyTheme(index, direction = 'next') {
        const theme = themes[index];
        document.documentElement.setAttribute('data-theme', theme.value);
        localStorage.setItem('selectedTheme', theme.value);
        document.cookie = `theme=${theme.value}; path=/; max-age=${365 * 24 * 60 * 60}; SameSite=Lax`;
        updateColorPaletteDisplay();
        animateThemeChange(theme.label, direction);
    }

    function addPressHandlers(btn) {
        if (!btn) return;
        const add = () => btn.classList.add('pressed');
        const remove = () => btn.classList.remove('pressed');
        btn.addEventListener('mousedown', add);
        btn.addEventListener('mouseup', remove);
        btn.addEventListener('mouseleave', remove);
        btn.addEventListener('touchstart', add, { passive: true });
        btn.addEventListener('touchend', remove);
        btn.addEventListener('touchcancel', remove);
    }

    if (themeDisplay) {
        const initLabel = document.createElement('span');
        initLabel.className = 'theme-label';
        initLabel.textContent = themes[currentIndex].label;
        themeDisplay.appendChild(initLabel);
    }

    if (themePrev && themeNext && themeDisplay) {
        addPressHandlers(themePrev);
        addPressHandlers(themeNext);

        themePrev.addEventListener('click', () => {
            currentIndex = (currentIndex - 1 + themes.length) % themes.length;
            applyTheme(currentIndex, 'prev');
        });
        themeNext.addEventListener('click', () => {
            currentIndex = (currentIndex + 1) % themes.length;
            applyTheme(currentIndex, 'next');
        });

        themeDisplay.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') {
                themePrev.click();
            } else if (e.key === 'ArrowRight') {
                themeNext.click();
            }
        });

        document.documentElement.setAttribute('data-theme', themes[currentIndex].value);
        localStorage.setItem('selectedTheme', themes[currentIndex].value);
        document.cookie = `theme=${themes[currentIndex].value}; path=/; max-age=${365 * 24 * 60 * 60}; SameSite=Lax`;
        updateColorPaletteDisplay();
    }

    document.querySelectorAll('.flashes .success').forEach(el => {
        setTimeout(() => {
            el.classList.add('fade-out');
            el.addEventListener('transitionend', () => el.remove(), { once: true });
        }, 3500);
    });

    const fileInput = document.getElementById('file-input');
    const fileInputLabel = document.querySelector('.file-input-label');
    const dropArea = document.getElementById('drop-area');
    const uploadForm = document.getElementById('upload-form');

    if (fileInput && fileInputLabel && dropArea && uploadForm) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                fileInputLabel.innerHTML = `<span class="material-icons">cloud_upload</span> ${fileInput.files[0].name}`;
            } else {
                fileInputLabel.innerHTML = `<span class="material-icons">cloud_upload</span> Drag & Drop files here or Click to select`;
            }
        });

        ['dragenter', 'dragover', 'drafeave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false); 
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => dropArea.classList.add('highlight'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => dropArea.classList.remove('highlight'), false);
        });

        dropArea.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;

            if (files.length > 0) {
                fileInput.files = files;
                fileInputLabel.innerHTML = `<span class="material-icons">cloud_upload</span> ${files[0].name}`;

            }
        }
    }

    updateColorPaletteDisplay();


});
