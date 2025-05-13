<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  interface Tag {
    id: number;
    name: string;
    post_count?: number;
  }

  let tags: Tag[] = [];
  let loading = true;
  let error: string | null = null;
  let search = '';

  async function fetchTags() {
    loading = true;
    error = null;
    try {
      const res = await fetch('/api/v1/tags');
      if (!res.ok) throw new Error(`Failed to fetch tags: ${res.status}`);
      tags = await res.json();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unknown error loading tags.';
    } finally {
      loading = false;
    }
  }

  onMount(fetchTags);

  function filteredTags() {
    if (!search.trim()) return tags;
    return tags.filter(tag => tag.name.toLowerCase().includes(search.trim().toLowerCase()));
  }

  function goToTag(tag: Tag) {
    goto(`/?tags=${encodeURIComponent(tag.name)}`);
  }
</script>

<div class="container mx-auto p-6">
  <div class="card bg-base-200 shadow-xl p-8 max-w-2xl mx-auto">
    <h1 class="text-3xl font-bold mb-4">Tags</h1>
    <input
      type="text"
      class="input input-bordered w-full mb-6"
      placeholder="Search tags..."
      bind:value={search}
    />
    {#if loading}
      <div class="flex justify-center items-center h-32">
        <span class="loading loading-lg"></span>
        <p class="ml-4">Loading tags...</p>
      </div>
    {:else if error}
      <div class="alert alert-error">{error}</div>
    {:else if filteredTags().length === 0}
      <p class="text-center text-gray-500">No tags found.</p>
    {:else}
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        {#each filteredTags() as tag}
          <button class="btn btn-outline btn-sm flex flex-col items-center" on:click={() => goToTag(tag)}>
            <span>{tag.name}</span>
            {#if tag.post_count !== undefined}
              <span class="text-xs text-gray-500">{tag.post_count} posts</span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>
