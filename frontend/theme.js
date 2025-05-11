document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '/api/v1'; // Consistent API base
    let serverThemeConfig = null;

    function applyServerThemeColors(themeName, themeData) {
        let styleSheet = document.getElementById('dynamic-theme-styles');
        if (!styleSheet) {
            styleSheet = document.createElement('style');
            styleSheet.id = 'dynamic-theme-styles';
            document.head.appendChild(styleSheet);
        }

        const themeColors = themeData[themeName];
        if (!themeColors) {
            console.warn(`Theme "${themeName}" not found in server configuration.`);
            // Fallback to ensure data-theme is set, CSS might have defaults
            document.documentElement.setAttribute('data-theme', themeName);
            return;
        }

        const cssVariables = Object.entries(themeColors)
            .map(([key, value]) => `--${key.replace(/_/g, '-')}: ${value};`)
            .join('\n');
        
        styleSheet.innerHTML = `
            html[data-theme="${themeName}"] {
                ${cssVariables}
            }
        `;
        // Ensure data-theme attribute is set for CSS selectors
        document.documentElement.setAttribute('data-theme', themeName);
    }

    async function loadAndApplyThemePreference() {
        try {
            const response = await fetch(`${API_BASE_URL}/theme-config`);
            if (!response.ok) {
                console.error('Failed to fetch theme configuration from server. Status:', response.status);
                applyLocalThemePreference(); // Fallback to local preference
                return;
            }
            serverThemeConfig = await response.json();
            
            const preferredTheme = localStorage.getItem('spectraTheme') || (serverThemeConfig.site && serverThemeConfig.site.default_theme) || 'dark'; 
            applyServerThemeColors(preferredTheme, serverThemeConfig);
            // applyServerThemeColors already sets data-theme

        } catch (error) {
            console.error('Error fetching or applying server theme configuration:', error);
            applyLocalThemePreference(); // Fallback
        }
    }
    
    function applyLocalThemePreference() {
        // This is a fallback if server config fails or for initial load before server config is fetched.
        // It primarily sets the data-theme attribute so basic CSS rules can apply.
        const preferredTheme = localStorage.getItem('spectraTheme') || 'dark';
        document.documentElement.setAttribute('data-theme', preferredTheme);
        // console.log(`Applied ${preferredTheme} theme using local preference (server config failed or not used).`);
    }

    // Initial theme load
    loadAndApplyThemePreference();

    // Theme Toggle Button - must be present on the page for this to work
    const themeToggleButton = document.getElementById('themeToggle');
    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            if (serverThemeConfig) {
                applyServerThemeColors(newTheme, serverThemeConfig);
            } else {
                // Fallback if serverThemeConfig isn't loaded, though loadAndApplyThemePreference should handle it
                document.documentElement.setAttribute('data-theme', newTheme);
            }
            // applyServerThemeColors already sets data-theme
            localStorage.setItem('spectraTheme', newTheme);
        });
    } else {
        // console.log("Theme toggle button not found on this page.");
    }
});
