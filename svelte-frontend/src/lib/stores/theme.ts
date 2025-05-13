// src/lib/stores/theme.ts
import { writable, type Writable } from 'svelte/store';

type ThemeConfig = Record<string, Record<string, string>> & {
	site?: { default_theme?: string }
};

function getInitialTheme(): string {
	if (typeof localStorage !== 'undefined') {
		const stored = localStorage.getItem('spectraTheme');
		if (stored) return stored;
	}
	return 'dark';
}

function applyThemeVariables(themeName: string, config: ThemeConfig | null) {
	let themeColors = config?.[themeName];
	if (!themeColors) {
		document.documentElement.setAttribute('data-theme', themeName);
		return;
	}
	const cssVariables = Object.entries(themeColors)
		.map(([key, value]) => `--${key.replace(/_/g, '-')}: ${value};`)
		.join('\n');
	let styleSheet = document.getElementById('dynamic-theme-styles') as HTMLStyleElement | null;
	if (!styleSheet) {
		styleSheet = document.createElement('style');
		styleSheet.id = 'dynamic-theme-styles';
		document.head.appendChild(styleSheet);
	}
	styleSheet.innerHTML = `
		html[data-theme="${themeName}"] {
			${cssVariables}
		}
	`;
	document.documentElement.setAttribute('data-theme', themeName);
}

function createThemeStore() {
	const { subscribe, set, update }: Writable<string> = writable(getInitialTheme());
	let config: ThemeConfig | null = null;

	async function fetchConfig() {
		try {
			const res = await fetch('/api/v1/theme-config');
			if (res.ok) {
				config = await res.json();
				// Ensure config is not null before accessing its properties
				const preferred = localStorage.getItem('spectraTheme') ||
					(config && config.site && config.site.default_theme) ||
					'dark';
				set(preferred);
				applyThemeVariables(preferred, config ?? null); // Pass config or null
			} else {
				config = null; // Explicitly set config to null on failure
				applyThemeVariables(getInitialTheme(), null);
			}
		} catch {
			config = null; // Explicitly set config to null on error
			applyThemeVariables(getInitialTheme(), null);
		}
	}

function toggle() {
update(current => {
const newTheme = current === 'dark' ? 'light' : 'dark';
localStorage.setItem('spectraTheme', newTheme);
applyThemeVariables(newTheme, config ?? null);
return newTheme;
});
}

	// On store initialization, fetch config and apply theme
	if (typeof window !== 'undefined') {
		fetchConfig();
	}

	return {
		subscribe,
		toggle
	};
}

export const theme = createThemeStore();
