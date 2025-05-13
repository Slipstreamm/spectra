<script lang="ts">
  import { auth, type User, type AuthState } from '$lib/stores/auth';
  import { goto } from '$app/navigation';
  import { onMount, onDestroy } from 'svelte';

  let currentUser: User | null = null;
  let isLoading = true; // Start with loading true until auth state is confirmed

  const unsubscribe = auth.subscribe((value: AuthState) => {
    currentUser = value.user;
    isLoading = value.loading;

    // Client-side redirect if not authenticated and not loading
    // A more robust solution would use a +layout.server.ts or +page.server.ts for route protection
    if (typeof window !== 'undefined' && !value.isAuthenticated && !value.loading) {
      goto('/login');
    }
  });

  onMount(() => {
    // Initial check in case store is already populated but component just mounted
    if (!$auth.isAuthenticated && !$auth.loading) {
        if (typeof window !== 'undefined') {
            goto('/login');
        }
    }
  });

  onDestroy(unsubscribe);

  function handleLogout() {
    auth.logout();
    // The subscription to auth store in +layout.svelte or individual pages
    // should ideally handle redirecting or updating UI after logout.
    // Forcing a redirect here ensures user is taken away from account page.
    if (typeof window !== 'undefined') {
        goto('/');
    }
  }
</script>

<div class="container mx-auto p-8">
  {#if isLoading}
    <div class="flex justify-center items-center h-64">
      <span class="loading loading-lg"></span>
      <p class="ml-4">Loading account details...</p>
    </div>
  {:else if currentUser}
    <div class="card p-6 bg-base-200 shadow-xl">
      <h1 class="text-3xl font-bold mb-6">My Account</h1>
      
      <div class="space-y-4">
        <div>
          <p class="font-semibold">Username:</p>
          <p>{currentUser.username}</p>
        </div>
        <div>
          <p class="font-semibold">Email:</p>
          <p>{currentUser.email}</p>
        </div>
        <div>
          <p class="font-semibold">Role:</p>
          <p class="capitalize">{currentUser.role}</p>
        </div>
        <div>
          <p class="font-semibold">Member Since:</p>
          <p>{new Date(currentUser.created_at).toLocaleDateString()}</p>
        </div>
        <div>
            <p class="font-semibold">Active Status:</p>
            <p>{currentUser.is_active ? 'Active' : 'Inactive'}</p>
        </div>
        {#if currentUser.is_superuser}
        <div>
            <p class="font-semibold">Permissions:</p>
            <p>Superuser</p>
        </div>
        {/if}
      </div>

      <div class="mt-8">
        <h2 class="text-xl font-semibold mb-4">Account Actions</h2>
        <!-- Placeholders for future actions -->
        <button class="btn btn-secondary mr-2" disabled>Update Profile (Soon)</button>
        <button class="btn btn-secondary" disabled>Change Password (Soon)</button>
      </div>

      <div class="mt-8 border-t pt-6">
        <button class="btn btn-error" on:click={handleLogout}>Logout</button>
      </div>
    </div>
  {:else}
    <!-- This case should ideally not be reached due to redirect, but as a fallback: -->
    <p class="text-center text-lg">You need to be logged in to view this page.</p>
    <div class="text-center mt-4">
        <a href="/login" class="btn btn-primary">Go to Login</a>
    </div>
  {/if}
</div>
