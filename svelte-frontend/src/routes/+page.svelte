<script lang="ts">
  // TODO: Import and use Svelte stores/components for gallery, user, theme, etc.
  import ThemeToggle from '$lib/components/ThemeToggle.svelte';
</script>

<header class="bg-primary p-4 flex justify-between items-center border-b border-border">
  <div class="flex items-center gap-4">
    <h1 class="text-2xl font-bold">Spectra Gallery</h1>
    <nav class="flex gap-4">
      <a href="/" class="active">Gallery</a>
      <a href="/upload/">Upload</a>
      <a href="/tags">Tags</a>
    </nav>
  </div>
  <div class="flex items-center gap-2">
    <ThemeToggle />
    <!-- TODO: User info and auth links as Svelte logic -->
    <span class="user-info-display hidden">Logged in as: <strong id="usernameDisplay"></strong></span>
    <a href="/login" class="user-link">Login</a>
    <a href="/register" class="user-link">Register</a>
    <a href="#" class="user-link hidden">Logout</a>
    <a href="/account" class="user-link hidden">My Account</a>
  </div>
</header>

<div class="flex">
  <aside class="w-80 p-4 border-r border-border">
    <div>
      <h2 class="font-semibold mb-2">Search</h2>
      <input type="text" placeholder="Enter tags (e.g., nature landscape)" class="input input-bordered w-full mb-2" />
      <button class="btn btn-primary w-full mb-4">Search Tags</button>
    </div>
    <div>
      <h2 class="font-semibold mb-2">Advanced Search</h2>
      <div class="mb-2">
        <label>Uploaded After:</label>
        <input type="date" class="input input-bordered w-full" />
      </div>
      <div class="mb-2">
        <label>Uploaded Before:</label>
        <input type="date" class="input input-bordered w-full" />
      </div>
      <div class="mb-2">
        <label>Min Score:</label>
        <input type="number" class="input input-bordered w-full" placeholder="e.g., 10" />
      </div>
      <div class="mb-2">
        <label>Min Width:</label>
        <input type="number" class="input input-bordered w-full" placeholder="e.g., 1920" />
      </div>
      <div class="mb-2">
        <label>Min Height:</label>
        <input type="number" class="input input-bordered w-full" placeholder="e.g., 1080" />
      </div>
      <div class="mb-2">
        <label>Uploader:</label>
        <input type="text" class="input input-bordered w-full" placeholder="Username" />
      </div>
      <button class="btn btn-secondary w-full">Apply Advanced Filters</button>
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
        <button class="btn btn-ghost btn-sm active">Latest</button>
        <button class="btn btn-ghost btn-sm">Popular</button>
        <button class="btn btn-ghost btn-sm">Random</button>
      </div>
      <div class="flex items-center gap-2">
        <label>Per page:</label>
        <select class="select select-bordered">
          <option>20</option>
          <option>50</option>
          <option>100</option>
        </select>
        <span>Size:</span>
        <button class="btn btn-ghost btn-xs">S</button>
        <button class="btn btn-ghost btn-xs active">M</button>
        <button class="btn btn-ghost btn-xs">L</button>
      </div>
    </div>
    <div class="gallery-grid">
      <!-- TODO: Gallery images will be loaded here by Svelte logic -->
      <p class="status-message">Loading images...</p>
    </div>
    <div>
      <!-- TODO: Pagination controls -->
    </div>
  </main>
</div>

<footer class="p-4 border-t border-border text-center">
  <p>&copy; 2024 Spectra Gallery. Inspired by minimalist designs.</p>
  <p><a href="/admin/">Admin Panel</a></p>
</footer>

<!-- TODO: Image Detail Modal as a Svelte component -->
