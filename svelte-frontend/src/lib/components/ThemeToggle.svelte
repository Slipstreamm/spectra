<script lang="ts">
  import { theme } from '../stores/theme';
  import { get } from 'svelte/store';

  // Optionally, you can use Skeleton UI's button if installed
  // import { Button } from '@skeletonlabs/skeleton';

  let currentTheme: string;
  const unsubscribe = theme.subscribe(value => {
    currentTheme = value;
  });

  function toggleTheme() {
    theme.toggle();
  }

  // Clean up subscription if needed (not strictly necessary for a simple button)
  // onDestroy(() => unsubscribe());
</script>

<button
  aria-label="Toggle theme"
  class="btn btn-ghost"
  on:click={toggleTheme}
  type="button"
>
  {#if currentTheme === 'dark'}
    🌙 Dark
  {:else}
    ☀️ Light
  {/if}
</button>
