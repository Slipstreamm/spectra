import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit()
	],
	server: {
		allowedHosts: [
			'localhost',
			'127.0.0.1',
			'spectra.slipstreamm.dev',
			'xbooru.xyz'
		],
		proxy: {
			'/api': {
				target: 'http://localhost:8000', // Assuming FastAPI runs on port 8000
				changeOrigin: true, // Recommended for virtual hosted sites
				secure: false, // Set to true if your backend is HTTPS and you have a valid cert
				// You might need rewrite if your backend API paths don't start with /api
				// rewrite: (path) => path.replace(/^\/api/, '') 
			}
		}
	}
});
