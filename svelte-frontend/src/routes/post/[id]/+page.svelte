<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let post: any = null;
  let loading = true;
  let error: string | null = null;

  $: postId = $page.params.id;

  async function fetchPost() {
    loading = true;
    error = null;
    try {
      const res = await fetch(`/api/v1/posts/${postId}`);
      if (!res.ok) throw new Error(`Failed to fetch post: ${res.status}`);
      post = await res.json();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unknown error loading post.';
    } finally {
      loading = false;
    }
  }

  onMount(fetchPost);
</script>

<div class="container mx-auto p-6">
  {#if loading}
    <div class="flex justify-center items-center h-64">
      <span class="loading loading-lg"></span>
      <p class="ml-4">Loading post...</p>
    </div>
  {:else if error}
    <div class="alert alert-error">{error}</div>
    <button class="btn btn-primary mt-4" on:click={() => goto('/')}>Back to Gallery</button>
  {:else if post}
    <div class="max-w-3xl mx-auto card bg-base-200 shadow-xl p-6">
      <img src={post.image_url} alt={post.title || post.filename} class="w-full rounded mb-4 object-contain max-h-96" />
      <h1 class="text-3xl font-bold mb-2">{post.title || post.filename}</h1>
      <p class="mb-2">{post.description}</p>
      <div class="mb-2 flex flex-wrap gap-1">
        {#each post.tags as tag}
          <span class="badge badge-outline">{tag.name}</span>
        {/each}
      </div>
      <div class="mb-2 text-sm text-gray-500">
        Uploaded by <span class="font-semibold">{post.uploader?.username ?? "unknown"}</span> on {new Date(post.uploaded_at).toLocaleDateString()}
      </div>
      <div class="flex gap-4 text-sm mt-2">
        <span>👍 {post.upvotes}</span>
        <span>💬 {post.comment_count}</span>
      </div>
      <div class="mt-6">
        <button class="btn btn-primary" on:click={() => goto('/')}>Back to Gallery</button>
      </div>
      <!-- Placeholder for comments section -->
      <div class="mt-8">
        <h2 class="text-xl font-semibold mb-2">Comments</h2>
        <p class="text-gray-500">Comments feature coming soon.</p>
      </div>
    </div>
  {/if}
</div>
