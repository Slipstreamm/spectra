<script lang="ts">
  import ThemeToggle from '$lib/components/ThemeToggle.svelte';
  import ImageModal from '$lib/components/ImageModal.svelte';
  import { auth, type AuthState } from '$lib/stores/auth';
  import { onDestroy, onMount } from 'svelte';

  let isAuthenticated = false;
  let username: string | null = null;

  const unsubscribeAuth = auth.subscribe((value: AuthState) => {
    isAuthenticated = value.isAuthenticated;
    username = value.user?.username ?? null;
  });

  onDestroy(() => {
    unsubscribeAuth();
  });

  function handleLogout() {
    auth.logout();
  }

  // Gallery logic
  interface PostForFrontend {
    id: number;
    filename: string;
    title?: string;
    description?: string;
    uploaded_at: string;
    uploader?: { id: number; username: string; role: string };
    tags: { name: string }[];
    image_url: string;
    thumbnail_url?: string;
    mimetype?: string;
    comment_count: number;
    upvotes: number;
    downvotes: number;
  }

  // Modal state
  let modalOpen = false;
  let selectedPost: PostForFrontend | null = null;

  function openModal(post: PostForFrontend) {
    selectedPost = post;
    modalOpen = true;
  }
  function closeModal() {
    modalOpen = false;
    selectedPost = null;
  }

  let posts: PostForFrontend[] = [];
  let loadingPosts = true;
  let postsError: string | null = null;

  // Pagination and filter state
  let currentPage = 1;
  let totalPages = 1;
  let perPage = 20;

  // Search/filter state
  let tagSearch = '';
  let filterDateAfter = '';
  let filterDateBefore = '';
  let filterMinScore = '';
  let filterMinWidth = '';
  let filterMinHeight = '';
  let filterUploader = '';

  // Sorting state
  let sortBy: string = 'date';
  let sortOrder: string = 'desc';

  // Fetch posts with current filters, sort, and pagination
  async function fetchPosts() {
    loadingPosts = true;
    postsError = null;
    let params = new URLSearchParams();
    params.set('page', currentPage.toString());
    params.set('limit', perPage.toString());
    if (tagSearch.trim()) params.set('tags', tagSearch.trim());
    if (filterDateAfter) params.set('uploaded_after', filterDateAfter);
    if (filterDateBefore) params.set('uploaded_before', filterDateBefore);
    if (filterMinScore) params.set('min_score', filterMinScore);
    if (filterMinWidth) params.set('min_width', filterMinWidth);
    if (filterMinHeight) params.set('min_height', filterMinHeight);
    if (filterUploader) params.set('uploader_name', filterUploader);
    if (sortBy) params.set('sort_by', sortBy);
    if (sortOrder) params.set('order', sortOrder);

    try {
      const res = await fetch(`/api/v1/posts?${params.toString()}`);
      if (!res.ok) throw new Error(`Failed to fetch posts: ${res.status}`);
      const data = await res.json();
      posts = data.data;
      totalPages = data.total_pages || 1;
    } catch (err) {
      postsError = err instanceof Error ? err.message : 'Unknown error loading posts.';
    } finally {
      loadingPosts = false;
    }
  }

  // Initial fetch
  onMount(fetchPosts);

  // Handlers for search/filter/sort/pagination controls
  function handleTagSearch() {
    currentPage = 1;
    fetchPosts();
  }
  function handleAdvancedSearch() {
    currentPage = 1;
    fetchPosts();
  }
  function handleSort(newSort: string) {
    if (sortBy === newSort) {
      sortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
    } else {
      sortBy = newSort;
      sortOrder = 'desc';
    }
    currentPage = 1;
    fetchPosts();
  }
  function handlePerPageChange(event: Event) {
    perPage = +(event.target as HTMLSelectElement).value;
    currentPage = 1;
    fetchPosts();
  }
  function handlePageChange(page: number) {
    if (page >= 1 && page <= totalPages) {
      currentPage = page;
      fetchPosts();
    }
  }
</script>

<header class="bg-primary p-4 flex justify-between items-center border-b border-border">
  <div class="flex items-center gap-4">
    <h1 class="text-2xl font-bold">Spectra Gallery</h1>
    <nav class="flex gap-4">
      <a href="/" class="hover:text-primary-focus">Gallery</a>
      {#if isAuthenticated}
        <a href="/upload" class="hover:text-primary-focus">Upload</a>
      {/if}
      <a href="/tags" class="hover:text-primary-focus">Tags</a>
    </nav>
  </div>
  <div class="flex items-center gap-2">
    <ThemeToggle />
    {#if isAuthenticated && username}
      <span class="mr-2">Hi, {username}!</span>
      <a href="/account" class="btn btn-sm btn-ghost">My Account</a>
      <button class="btn btn-sm btn-ghost" on:click={handleLogout}>Logout</button>
    {:else}
      <a href="/login" class="btn btn-sm btn-ghost">Login</a>
      <a href="/register" class="btn btn-sm btn-ghost">Register</a>
    {/if}
  </div>
</header>

<div class="flex">
  <aside class="w-80 p-4 border-r border-border">
    <div>
      <h2 class="font-semibold mb-2">Search</h2>
      <input
        type="text"
        placeholder="Enter tags (e.g., nature landscape)"
        class="input input-bordered w-full mb-2"
        bind:value={tagSearch}
        on:keydown={(e) => { if (e.key === 'Enter') { handleTagSearch(); } }}
      />
      <button class="btn btn-primary w-full mb-4" on:click={handleTagSearch}>Search Tags</button>
    </div>
    <div>
      <h2 class="font-semibold mb-2">Advanced Search</h2>
      <div class="mb-2">
        <label>Uploaded After:</label>
        <input type="date" class="input input-bordered w-full" bind:value={filterDateAfter} />
      </div>
      <div class="mb-2">
        <label>Uploaded Before:</label>
        <input type="date" class="input input-bordered w-full" bind:value={filterDateBefore} />
      </div>
      <div class="mb-2">
        <label>Min Score:</label>
        <input type="number" class="input input-bordered w-full" placeholder="e.g., 10" bind:value={filterMinScore} />
      </div>
      <div class="mb-2">
        <label>Min Width:</label>
        <input type="number" class="input input-bordered w-full" placeholder="e.g., 1920" bind:value={filterMinWidth} />
      </div>
      <div class="mb-2">
        <label>Min Height:</label>
        <input type="number" class="input input-bordered w-full" placeholder="e.g., 1080" bind:value={filterMinHeight} />
      </div>
      <div class="mb-2">
        <label>Uploader:</label>
        <input type="text" class="input input-bordered w-full" placeholder="Username" bind:value={filterUploader} />
      </div>
      <button class="btn btn-secondary w-full" on:click={handleAdvancedSearch}>Apply Advanced Filters</button>
    </div>
    <div class="mt-6">
      <h3 class="font-semibold mb-2">Tags</h3>
      <input type="text" placeholder="Filter tags..." class="input input-bordered w-full mb-2" />
      <div>
        <h4 class="font-semibold">Copyright</h4>
        <ul>
          <li><a href="#">tag_a (123)</a></li>
          <li><a href="#">another_tag (45)</a></li>
        </ul>
        <h4 class="font-semibold">Character</h4>
        <ul>
          <li><a href="#">character_x (78)</a></li>
        </ul>
        <h4 class="font-semibold">General</h4>
        <ul>
          <li><a href="#">general_topic (200)</a></li>
          <li><a href="#">more_general (90)</a></li>
        </ul>
      </div>
    </div>
  </aside>
  <main class="flex-1 p-4">
    <div class="flex justify-between items-center mb-4">
      <div>
        <span>Sort by:</span>
        <button class="btn btn-ghost btn-sm {sortBy === 'date' ? 'active' : ''}" on:click={() => handleSort('date')}>Latest</button>
        <button class="btn btn-ghost btn-sm {sortBy === 'score' ? 'active' : ''}" on:click={() => handleSort('score')}>Popular</button>
        <button class="btn btn-ghost btn-sm {sortBy === 'random' ? 'active' : ''}" on:click={() => handleSort('random')}>Random</button>
      </div>
      <div class="flex items-center gap-2">
        <label>Per page:</label>
        <select class="select select-bordered" bind:value={perPage} on:change={handlePerPageChange}>
          <option value="20">20</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select>
        <span>Size:</span>
        <button class="btn btn-ghost btn-xs">S</button>
        <button class="btn btn-ghost btn-xs active">M</button>
        <button class="btn btn-ghost btn-xs">L</button>
      </div>
    </div>
    <div class="gallery-grid grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
      {#if loadingPosts}
        <p class="status-message col-span-full text-center">Loading images...</p>
      {:else if postsError}
        <p class="status-message col-span-full text-error text-center">{postsError}</p>
      {:else if posts.length === 0}
        <p class="status-message col-span-full text-center">No images found.</p>
      {:else}
        {#each posts as post}
          <div class="card bg-base-200 shadow-md p-2 flex flex-col cursor-pointer" on:click={() => openModal(post)}>
            <img src={post.thumbnail_url || post.image_url} alt={post.title || post.filename} class="rounded w-full object-cover aspect-[4/3] mb-2" loading="lazy" />
            <div class="flex-1 flex flex-col justify-between">
              <div>
                <h2 class="font-semibold text-lg truncate">{post.title || post.filename}</h2>
                <p class="text-xs text-gray-500">by {post.uploader?.username ?? "unknown"}</p>
              </div>
              <div class="flex flex-wrap gap-1 mt-2">
                {#each post.tags as tag}
                  <span class="badge badge-outline">{tag.name}</span>
                {/each}
              </div>
              <div class="flex justify-between items-center mt-2 text-xs">
                <span>👍 {post.upvotes}</span>
                <span>💬 {post.comment_count}</span>
                <span>{new Date(post.uploaded_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        {/each}
      {/if}
    </div>
    <div class="flex justify-center mt-8 gap-2">
      {#if totalPages > 1}
        <button class="btn btn-sm" on:click={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1}>Prev</button>
        {#each Array(totalPages) as _, i}
          <button
            class="btn btn-sm {currentPage === i + 1 ? 'btn-primary' : ''}"
            on:click={() => handlePageChange(i + 1)}
            disabled={currentPage === i + 1}
          >
            {i + 1}
          </button>
        {/each}
        <button class="btn btn-sm" on:click={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages}>Next</button>
      {/if}
    </div>
  </main>
</div>

<footer class="p-4 border-t border-border text-center">
  <p>&copy; 2024 Spectra Gallery. Inspired by minimalist designs.</p>
  <p><a href="/admin/">Admin Panel</a></p>
</footer>

<ImageModal open={modalOpen} post={selectedPost} onClose={closeModal} />
