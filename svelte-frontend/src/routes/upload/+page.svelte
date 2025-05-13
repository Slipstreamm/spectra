<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  let file: File | null = null;
  let tags = '';
  let status: string | null = null;
  let error: string | null = null;
  let uploading = false;

  let isAuthenticated = false;
  let token: string | null = null;

  const unsubscribe = auth.subscribe((value) => {
    isAuthenticated = value.isAuthenticated;
    token = value.token;
  });

  onMount(() => {
    if (!isAuthenticated) {
      goto('/login');
    }
  });

  async function handleUpload(e: Event) {
    e.preventDefault();
    status = null;
    error = null;

    if (!file) {
      error = 'Please select an image file.';
      return;
    }
    if (!token) {
      error = 'You must be logged in to upload.';
      return;
    }

    uploading = true;
    const formData = new FormData();
    formData.append('file', file);
    if (tags.trim()) {
      formData.append('tags_str', tags.trim());
    }

    try {
      const res = await fetch('/api/v1/posts/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed: ${res.status}`);
      }

      status = 'Image uploaded successfully!';
      file = null;
      tags = '';
    } catch (err) {
      error = err instanceof Error ? err.message : 'Unknown error during upload.';
    } finally {
      uploading = false;
    }
  }
</script>

<div class="container mx-auto p-6 max-w-xl">
  <div class="card bg-base-200 shadow-xl p-8">
    <h2 class="text-2xl font-bold mb-4">Upload New Image</h2>
    <form on:submit|preventDefault={handleUpload}>
      <div class="mb-4">
        <label class="block mb-1 font-semibold" for="imageFile">Choose image:</label>
        <input
          type="file"
          id="imageFile"
          name="imageFile"
          accept="image/png, image/jpeg, image/gif, image/webp"
          required
          on:change={(e) => { file = (e.target as HTMLInputElement).files?.[0] ?? null; }}
          class="input input-bordered w-full"
        />
      </div>
      <div class="mb-4">
        <label class="block mb-1 font-semibold" for="imageTags">Tags (comma-separated):</label>
        <input
          type="text"
          id="imageTags"
          name="imageTags"
          placeholder="e.g., nature, cat, funny"
          bind:value={tags}
          class="input input-bordered w-full"
        />
      </div>
      <button type="submit" class="btn btn-primary w-full" disabled={uploading}>
        {#if uploading}
          <span class="loading loading-spinner"></span> Uploading...
        {:else}
          Upload Image
        {/if}
      </button>
    </form>
    {#if status}
      <div class="alert alert-success mt-4">{status}</div>
    {/if}
    {#if error}
      <div class="alert alert-error mt-4">{error}</div>
    {/if}
  </div>
</div>
