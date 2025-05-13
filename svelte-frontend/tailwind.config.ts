import type { Config } from 'tailwindcss';
import skeleton from '@skeletonlabs/tw-plugin';
import typography from '@tailwindcss/typography';
import { myCustomTheme } from './skeleton.config';

export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {}
  },
  presets: [skeleton],
  plugins: [
    typography,
    skeleton
  ]
} as Config;
