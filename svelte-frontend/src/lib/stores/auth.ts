// src/lib/stores/auth.ts
import { writable, type Writable } from 'svelte/store';

export type UserRole = "owner" | "admin" | "moderator" | "user";

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string; // ISO datetime string
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  error: string | null;
  loading: boolean;
}

const initialAuthState: AuthState = {
  isAuthenticated: false,
  user: null,
  token: null,
  error: null,
  loading: false,
};

function createAuthStore() {
  const { subscribe, set, update }: Writable<AuthState> = writable(initialAuthState);

  async function fetchCurrentUser(token: string): Promise<void> {
    update(state => ({ ...state, loading: true, error: null }));
    try {
      const response = await fetch('/api/v1/users/me', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) { // Unauthorized, token might be invalid/expired
          logout(); // Clear invalid token and reset state
        }
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch user details.' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const userData: User = await response.json();
      update(state => ({
        ...state,
        isAuthenticated: true,
        user: userData,
        token: token, // Ensure token is also set here
        loading: false,
        error: null,
      }));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
      // console.error('Fetch current user error:', errorMessage);
      // Don't clear token here if it's just a network error, only on 401
      update(state => ({ ...state, loading: false, error: errorMessage }));
      if (! (err instanceof Error && err.message.includes("HTTP error! status: 401"))) {
        // If not a 401, it might be a temporary issue, don't logout immediately
      }
    }
  }

  // Attempt to load token from localStorage on initialization
  if (typeof localStorage !== 'undefined') {
    const storedToken = localStorage.getItem('authToken');
    if (storedToken) {
      fetchCurrentUser(storedToken);
    }
  }

  async function login(usernameInput: string, passwordInput: string): Promise<boolean> {
    update(state => ({ ...state, loading: true, error: null }));
    try {
      const response = await fetch('/api/v1/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          username: usernameInput,
          password: passwordInput,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed. Invalid server response.' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data: { access_token: string, token_type: string } = await response.json();

      if (data.access_token) {
        localStorage.setItem('authToken', data.access_token);
        await fetchCurrentUser(data.access_token); // Fetch user details with the new token
        return true; // Indicate login success
      } else {
        throw new Error('Access token not found in response.');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred during login.';
      update(state => ({
        ...state,
        isAuthenticated: false,
        user: null,
        token: null,
        error: errorMessage,
        loading: false,
      }));
      // console.error('Login error:', errorMessage);
      return false; // Indicate login failure
    }
  }

  function logout() {
    localStorage.removeItem('authToken');
    set(initialAuthState); // Reset to initial state
  }

  async function register(usernameInput: string, emailInput: string, passwordInput: string): Promise<{ success: boolean; error?: string; user?: User }> {
    update(state => ({ ...state, loading: true, error: null }));
    try {
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: usernameInput,
          email: emailInput,
          password: passwordInput,
        }),
      });

      const responseData = await response.json();

      if (!response.ok) { // Handles 400, 422 etc.
        throw new Error(responseData.detail || `HTTP error! status: ${response.status}`);
      }
      
      // response.status === 201 for successful registration
      // The response body is the created user
      update(state => ({ ...state, loading: false, error: null }));
      return { success: true, user: responseData as User };

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred during registration.';
      update(state => ({
        ...state,
        error: errorMessage,
        loading: false,
      }));
      // console.error('Registration error:', errorMessage);
      return { success: false, error: errorMessage };
    }
  }

  return {
    subscribe,
    login,
    logout,
    register,
    fetchCurrentUser // Expose if needed for manual refresh, though typically handled internally
  };
}

export const auth = createAuthStore();
