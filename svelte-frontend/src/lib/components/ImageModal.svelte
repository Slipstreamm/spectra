<script lang="ts">
  export let post: any = null;
  export let open = false;
  export let onClose: () => void = () => {};

  function handleBackgroundClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }
</script>

{#if open && post}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60" on:click={handleBackgroundClick}>
    <div class="bg-base-100 rounded-lg shadow-lg max-w-2xl w-full p-6 relative">
      <button class="absolute top-2 right-2 btn btn-sm btn-circle btn-ghost" on:click={onClose} aria-label="Close">&times;</button>
      <img src={post.image_url} alt={post.title || post.filename} class="w-full rounded mb-4 object-contain max-h-96" />
      <h2 class="text-2xl font-bold mb-2">{post.title || post.filename}</h2>
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
      <div class="mt-4">
        <a href={"/post/" + post.id} class="btn btn-primary btn-sm">View Full Details</a>
      </div>
    </div>
  </div>
{/if}
