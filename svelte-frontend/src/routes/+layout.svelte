<script lang="ts">
    import '@skeletonlabs/skeleton/themes/theme-skeleton.css';
    import ThemeToggle from '$lib/components/ThemeToggle.svelte';
</script>

<div class="p-4">
    <ThemeToggle />
</div>

<slot />
