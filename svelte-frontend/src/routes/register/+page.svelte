<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { goto } from '$app/navigation';
  import { onDestroy } from 'svelte';

  let username = '';
  let email = '';
  let password = '';
  let confirmPassword = '';

  let currentError: string | null = null;
  let successMessage: string | null = null;
  let currentLoading = false;

  // Subscribe to loading state from the auth store if needed,
  // or manage it locally for the register action.
  // For simplicity, we'll manage loading locally for this specific action.
  // const unsubscribe = auth.subscribe(value => {
  //   currentLoading = value.loading; // This might reflect global auth loading
  // });
  // onDestroy(unsubscribe);


  async function handleRegister() {
    currentError = null;
    successMessage = null;

    if (password !== confirmPassword) {
      currentError = 'Passwords do not match.';
      return;
    }
    if (!username || !email || !password) {
      currentError = 'All fields are required.';
      return;
    }

    currentLoading = true;
    const result = await auth.register(username, email, password);
    currentLoading = false;

    if (result.success && result.user) {
      successMessage = `User ${result.user.username} registered successfully! Please login.`;
      // Optionally redirect to login page after a short delay or on button click
      setTimeout(() => {
        if (typeof window !== 'undefined') {
            goto('/login');
        }
      }, 2000); // Redirect after 2 seconds
    } else {
      currentError = result.error || 'Registration failed. Please try again.';
    }
  }
</script>

<div class="container mx-auto p-4 flex justify-center items-center min-h-screen">
  <div class="card p-8 shadow-xl w-full max-w-md">
    <h1 class="text-3xl font-bold text-center mb-6">Register for Spectra</h1>
    <form on:submit|preventDefault={handleRegister}>
      <div class="space-y-4">
        <label class="label">
          <span>Username</span>
          <input class="input input-bordered w-full" type="text" bind:value={username} required minlength="3" maxlength="50" placeholder="choose_a_username" />
        </label>
        <label class="label">
          <span>Email</span>
          <input class="input input-bordered w-full" type="email" bind:value={email} required placeholder="your_email@example.com" />
        </label>
        <label class="label">
          <span>Password</span>
          <input class="input input-bordered w-full" type="password" bind:value={password} required minlength="8" placeholder="choose_a_strong_password" />
        </label>
        <label class="label">
          <span>Confirm Password</span>
          <input class="input input-bordered w-full" type="password" bind:value={confirmPassword} required minlength="8" placeholder="re-enter_your_password" />
        </label>
      </div>

      {#if currentError}
        <p class="alert alert-error text-sm mt-4 text-center p-2">{currentError}</p>
      {/if}
      {#if successMessage}
        <p class="alert alert-success text-sm mt-4 text-center p-2">{successMessage}</p>
      {/if}

      <div class="mt-6">
        <button type="submit" class="btn btn-primary w-full" disabled={currentLoading}>
          {#if currentLoading}
            <span class="loading loading-spinner"></span>
            Registering...
          {:else}
            Register
          {/if}
        </button>
      </div>
    </form>
    <p class="text-center mt-6">
      Already have an account? <a href="/login" class="link link-primary">Login here</a>.
    </p>
  </div>
</div>

<style>
  .min-h-screen {
    min-height: calc(100vh - var(--header-height, 4rem)); /* Adjust if you have a fixed header */
  }
</style>
