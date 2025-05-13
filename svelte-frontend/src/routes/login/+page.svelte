<script lang="ts">
  import { auth, type AuthState } from '$lib/stores/auth';
  import { goto } from '$app/navigation';
  import { onDestroy } from 'svelte';

  let username = '';
  let password = '';
  let currentError: string | null = null;
  let currentLoading = false;

  const unsubscribe = auth.subscribe((value: AuthState) => {
    currentError = value.error;
    currentLoading = value.loading;
    if (value.isAuthenticated) {
      // User is authenticated, redirect to home or dashboard
      // Check if we are on the client side before redirecting
      if (typeof window !== 'undefined') {
        goto('/'); // Or a more appropriate page like /account
      }
    }
  });

  onDestroy(unsubscribe);

  async function handleLogin() {
    if (!username || !password) {
      currentError = 'Username and password are required.';
      return;
    }
    const success = await auth.login(username, password);
    // Redirection is handled by the store subscription
    // if (success) {
    //   // No need to redirect here, subscription will handle it
    // }
  }
</script>

<div class="container mx-auto p-4 flex justify-center items-center min-h-screen">
  <div class="card p-8 shadow-xl w-full max-w-md">
    <h1 class="text-3xl font-bold text-center mb-6">Login to Spectra</h1>
    <form on:submit|preventDefault={handleLogin}>
      <div class="space-y-4">
        <label class="label">
          <span>Username or Email</span>
          <input class="input input-bordered w-full" type="text" bind:value={username} required placeholder="your_username_or_email" />
        </label>
        <label class="label">
          <span>Password</span>
          <input class="input input-bordered w-full" type="password" bind:value={password} required placeholder="your_password" />
        </label>
      </div>
      {#if currentError}
        <p class="text-error text-sm mt-4 text-center">{currentError}</p>
      {/if}
      <div class="mt-6">
        <button type="submit" class="btn btn-primary w-full" disabled={currentLoading}>
          {#if currentLoading}
            <span class="loading loading-spinner"></span>
            Logging in...
          {:else}
            Login
          {/if}
        </button>
      </div>
    </form>
    <p class="text-center mt-6">
      Don't have an account? <a href="/register" class="link link-primary">Register here</a>.
    </p>
  </div>
</div>

<style>
  /* Add any page-specific styles here if needed, though Tailwind/Skeleton should cover most */
  .min-h-screen {
    min-height: calc(100vh - var(--header-height, 4rem)); /* Adjust if you have a fixed header */
  }
</style>
