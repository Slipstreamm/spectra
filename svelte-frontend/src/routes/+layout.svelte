<script lang="ts">
    import '../app.css';
    import '@skeletonlabs/skeleton/styles/all.css';
    import '@skeletonlabs/skeleton/styles/skeleton.css';
    import ThemeToggle from '$lib/components/ThemeToggle.svelte';
</script>

<div class="p-4">
    <ThemeToggle />
</div>

<slot />
