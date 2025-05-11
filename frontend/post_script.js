document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const postTitleElement = document.getElementById('postTitle');
    const postUploaderElement = document.getElementById('postUploader');
    const postUploadedAtElement = document.getElementById('postUploadedAt');
    const postImageElement = document.getElementById('postImage');
    const postDescriptionTextElement = document.getElementById('postDescriptionText');
    const postTagsContainer = document.getElementById('postTags');
    const postVoteScoreElement = document.getElementById('postVoteScore');
    const postVoteSection = document.querySelector('.post-actions .vote-section');

    const commentsListElement = document.getElementById('commentsList');
    const commentCountElement = document.getElementById('commentCount');
    const commentForm = document.getElementById('commentForm');
    const commentTextElement = document.getElementById('commentText');
    const submitCommentButton = document.getElementById('submitComment');
    const commentErrorElement = document.getElementById('commentError');

    // Header Auth DOM Elements (using "Header" suffix from post.html)
    const themeToggleHeaderButton = document.getElementById('themeToggleHeader');
    const loginLinkHeader = document.getElementById('loginLinkHeader');
    const registerLinkHeader = document.getElementById('registerLinkHeader');
    const logoutLinkHeader = document.getElementById('logoutLinkHeader');
    const userInfoHeaderDisplay = document.getElementById('userInfoHeader');
    const usernameDisplayHeader = document.getElementById('usernameDisplayHeader');

    // Footer year
    const currentYearElement = document.getElementById('currentYear');


    // API and App State
    const API_BASE_URL = '/api/v1';
    let currentPostId = null;
    // let currentUser = null; // 'currentUser' was declared but not really used, getAuthToken and getUsername are preferred

    // --- Utility Functions ---
    function getAuthToken() {
        return localStorage.getItem('authToken'); // Assuming token is stored here after login
    }

    function getUsername() {
        return localStorage.getItem('username');
    }

    function getUserRole() {
        return localStorage.getItem('userRole');
    }

    async function fetchWithAuth(url, options = {}) {
        const token = getAuthToken();
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    // --- Post Loading and Rendering ---
    async function loadPostDetails(postId) {
        try {
            const post = await fetchWithAuth(`${API_BASE_URL}/posts/${postId}`);
            renderPost(post);
            await loadComments(postId); // Load comments after post is loaded
        } catch (error) {
            console.error('Error loading post details:', error);
            document.getElementById('postDetailContainer').innerHTML =
                `<p class="status-message error-message">Error loading post: ${error.message}</p>`;
        }
    }

    function renderPost(post) {
        currentPostId = post.id;
        postTitleElement.textContent = post.title || 'Untitled Post';
        const uploaderName = post.uploader ? post.uploader.username : 'Unknown';
        const uploaderRole = post.uploader && post.uploader.role ? post.uploader.role : '';
        postUploaderElement.textContent = `By: ${uploaderName}${uploaderRole && uploaderRole !== 'user' ? ' (' + uploaderRole + ')' : ''}`;
        postUploadedAtElement.textContent = `Uploaded: ${new Date(post.uploaded_at).toLocaleString()}`;

        if (post.image_url) {
            postImageElement.src = post.image_url;
            postImageElement.alt = post.title || post.filename || 'Post image';
        } else if (post.filename) { // Fallback for older data or if image_url is not present
             postImageElement.src = `${API_BASE_URL}/static/uploads/${post.filename}`;
             postImageElement.alt = post.title || post.filename || 'Post image';
        } else {
            postImageElement.style.display = 'none'; // Hide if no image source
        }

        postDescriptionTextElement.textContent = post.description || 'No description provided.';

        postTagsContainer.innerHTML = '';
        if (post.tags && post.tags.length > 0) {
            post.tags.forEach(tag => {
                const tagSpan = document.createElement('span');
                tagSpan.textContent = tag.name;
                // Optional: Make tags clickable to go to main gallery with tag filter
                tagSpan.addEventListener('click', () => {
                    window.location.href = `index.html?tags=${encodeURIComponent(tag.name)}`;
                });
                postTagsContainer.appendChild(tagSpan);
            });
        } else {
            postTagsContainer.textContent = 'No tags.';
        }

        updateVoteDisplay('post', post.id, post.upvotes, post.downvotes, post.user_vote);
        postVoteSection.dataset.targetId = post.id; // Set target ID for voting
    }

    // --- Voting Logic ---
    function updateVoteDisplay(targetType, targetId, upvotes, downvotes, userVote) {
        const scoreElement = targetType === 'post' ? postVoteScoreElement : document.querySelector(`.comment-item[data-comment-id="${targetId}"] .vote-score`);
        const voteSectionElement = targetType === 'post' ? postVoteSection : document.querySelector(`.comment-item[data-comment-id="${targetId}"] .vote-section`);

        if (scoreElement) {
            scoreElement.textContent = (upvotes || 0) - (downvotes || 0);
        }

        if (voteSectionElement) {
            const upvoteButton = voteSectionElement.querySelector('.upvote');
            const downvoteButton = voteSectionElement.querySelector('.downvote');

            upvoteButton.classList.remove('active');
            downvoteButton.classList.remove('active');

            if (userVote === 1) { // Upvoted
                upvoteButton.classList.add('active');
            } else if (userVote === -1) { // Downvoted
                downvoteButton.classList.add('active');
            }
        }
    }

    async function handleVote(event) {
        if (!getAuthToken()) {
            alert('Please log in to vote.');
            // Potentially redirect to login or show a login modal
            return;
        }

        const button = event.target.closest('.vote-button');
        if (!button) return;

        const voteSection = button.closest('.vote-section');
        const targetType = voteSection.dataset.targetType; // 'post' or 'comment'
        const targetId = voteSection.dataset.targetId;
        const voteType = button.dataset.voteType; // 'upvote' or 'downvote'

        // Determine the vote value: 1 for upvote, -1 for downvote.
        // If the clicked button is already active, it means the user is unvoting.
        let currentVoteValue = 0;
        if (targetType === 'post') {
            const postData = await fetchWithAuth(`${API_BASE_URL}/posts/${targetId}`); // Re-fetch to get current user_vote
            currentVoteValue = postData.user_vote || 0;
        } else if (targetType === 'comment') {
             // For comments, we might need to fetch comment details if user_vote isn't readily available
             // Or, assume the UI state is accurate enough for toggling. For simplicity, let's assume we might need to fetch.
             // This could be optimized by storing user_vote on the comment object when initially fetched.
            const comments = await fetchWithAuth(`${API_BASE_URL}/posts/${currentPostId}/comments/`);
            const commentData = comments.data.find(c => c.id.toString() === targetId.toString());
            if (commentData) currentVoteValue = commentData.user_vote || 0;
        }


        // The backend handles toggling by checking if the same vote type is submitted
        // If user clicks the same vote button again, the backend will remove the vote
        let newVoteValue;
        if (voteType === 'upvote') {
            newVoteValue = 1; // Always send 1 for upvote
        } else { // downvote
            newVoteValue = -1; // Always send -1 for downvote
        }

        try {
            // Backend expects post_id or comment_id, not target_type and target_id
            const payload = {
                vote_type: newVoteValue // Backend only accepts -1 or 1
            };

            // Set the appropriate ID field based on target type
            if (targetType === 'post') {
                payload.post_id = parseInt(targetId);
            } else if (targetType === 'comment') {
                payload.comment_id = parseInt(targetId);
            }

            // The backend will handle toggling - if the user already has the same vote type,
            // it will remove the vote (unvote)

            const result = await fetchWithAuth(`${API_BASE_URL}/votes/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            updateVoteDisplay(targetType, targetId, result.upvotes, result.downvotes, result.user_vote);

        } catch (error) {
            console.error(`Error casting ${targetType} vote:`, error);
            alert(`Failed to cast vote: ${error.message}`);
        }
    }

    postVoteSection.addEventListener('click', handleVote);


    // --- Comments Logic ---
    async function loadComments(postId) {
        commentsListElement.innerHTML = '<p class="status-message">Loading comments...</p>';
        try {
            const commentsData = await fetchWithAuth(`${API_BASE_URL}/posts/${postId}/comments/`);
            renderComments(commentsData.data || []);
            commentCountElement.textContent = commentsData.total_items || 0;
        } catch (error) {
            console.error('Error loading comments:', error);
            commentsListElement.innerHTML = `<p class="status-message error-message">Error loading comments: ${error.message}</p>`;
        }
    }

    function renderComments(comments) {
        commentsListElement.innerHTML = '';
        if (comments.length === 0) {
            commentsListElement.innerHTML = '<p class="status-message">No comments yet. Be the first to comment!</p>';
            return;
        }

        comments.forEach(comment => {
            const commentItem = document.createElement('div');
            commentItem.className = 'comment-item';
            commentItem.dataset.commentId = comment.id;

            // Use comment.user which is UserBase (includes role if backend sends it)
            const commenterName = comment.user ? comment.user.username : 'Anonymous';
            const commenterRole = comment.user && comment.user.role ? comment.user.role : '';
            const commentDate = new Date(comment.created_at).toLocaleString();

            const commenterDisplay = `${commenterName}${commenterRole && commenterRole !== 'user' ? ' (' + commenterRole + ')' : ''}`;

            commentItem.innerHTML = `
                <div class="comment-meta">
                    <span class="commenter-username">${commenterDisplay}</span> -
                    <span class="comment-timestamp">${commentDate}</span>
                </div>
                <p class="comment-content">${comment.content}</p>
                <div class="comment-actions">
                    <div class="vote-section" data-target-type="comment" data-target-id="${comment.id}">
                        <button class="vote-button upvote" data-vote-type="upvote">Upvote</button>
                        <span class="vote-score">${(comment.upvotes || 0) - (comment.downvotes || 0)}</span>
                        <button class="vote-button downvote" data-vote-type="downvote">Downvote</button>
                    </div>
                    <button class="reply-button" data-comment-id="${comment.id}" data-commenter-username="${commenterName}">Reply</button>
                </div>
            `;
            // Add event listener for comment votes
            commentItem.querySelector('.vote-section').addEventListener('click', handleVote);

            // Update initial vote display for the comment
            updateVoteDisplay('comment', comment.id, comment.upvotes, comment.downvotes, comment.user_vote);

            // Add event listener for reply button
            const replyButton = commentItem.querySelector('.reply-button');
            if (replyButton) {
                // Update dataset to use commenterName for @mention consistency
                replyButton.dataset.commenterUsername = commenterName;
                replyButton.addEventListener('click', handleReplyClick);
            }

            commentsListElement.appendChild(commentItem);
        });
    }

    function handleReplyClick(event) {
        if (!getAuthToken()) {
            alert('Please log in to reply.');
            return;
        }
        const targetCommentId = event.target.dataset.commentId;
        const commenterUsernameForMention = event.target.dataset.commenterUsername; // Use the name part for @mention

        commentTextElement.value = `@${commenterUsernameForMention} `;
        commentTextElement.focus();
        commentForm.dataset.replyToCommentId = targetCommentId;
    }

    commentForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!getAuthToken()) {
            commentErrorElement.textContent = 'Please log in to comment.';
            commentErrorElement.style.display = 'block';
            return;
        }
        if (!currentPostId) {
            commentErrorElement.textContent = 'Cannot submit comment: Post ID is missing.';
            commentErrorElement.style.display = 'block';
            return;
        }

        const content = commentTextElement.value.trim();
        if (!content) {
            commentErrorElement.textContent = 'Comment cannot be empty.';
            commentErrorElement.style.display = 'block';
            return;
        }

        submitCommentButton.disabled = true;
        commentErrorElement.style.display = 'none';

        try {
            const payload = { content: content };
            const replyToCommentId = commentForm.dataset.replyToCommentId;

            if (replyToCommentId) {
                payload.parent_id = parseInt(replyToCommentId);
            }

            await fetchWithAuth(`${API_BASE_URL}/posts/${currentPostId}/comments/`, {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            commentTextElement.value = ''; // Clear textarea
            delete commentForm.dataset.replyToCommentId; // Clear reply state
            await loadComments(currentPostId); // Refresh comments list
        } catch (error) {
            console.error('Error posting comment:', error);
            commentErrorElement.textContent = `Failed to post comment: ${error.message}`;
            commentErrorElement.style.display = 'block';
        } finally {
            submitCommentButton.disabled = false;
        }
    });


    // --- Initialization ---
    function init() {
        const urlParams = new URLSearchParams(window.location.search);
        const postIdFromUrl = urlParams.get('id');

        if (postIdFromUrl) {
            loadPostDetails(postIdFromUrl);
        } else {
            document.getElementById('postDetailContainer').innerHTML =
                '<p class="status-message error-message">No post ID provided in URL.</p>';
        }

        // Check auth status and update UI (e.g., show/hide comment form, login links)
        updateAuthUI(); // Call this to set header links too

        if (!getAuthToken()) {
            if (commentForm) commentForm.style.display = 'none'; // Hide comment form if not logged in

            const authMessageElement = document.getElementById('authMessagePlaceholder');
            if (authMessageElement) { // If placeholder exists, update it
                authMessageElement.innerHTML = 'You must be <a href="login.html">logged in</a> to comment or vote.';
            } else { // Otherwise, create and append it
                const placeholder = document.createElement('p');
                placeholder.id = 'authMessagePlaceholder';
                placeholder.className = 'status-message'; // Use existing class for styling
                placeholder.innerHTML = 'You must be <a href="login.html">logged in</a> to comment or vote.'; // Assuming login.html
                if (commentsListElement) commentsListElement.insertAdjacentElement('afterend', placeholder);
            }
        } else {
             if (commentForm) commentForm.style.display = 'block';
             const authMessageElement = document.getElementById('authMessagePlaceholder');
             if (authMessageElement) authMessageElement.style.display = 'none'; // Hide if user is logged in
        }

        // Theme toggle logic (moved from inline script)
        if (themeToggleHeaderButton) {
            themeToggleHeaderButton.addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('spectraTheme', newTheme);
                // If server-side theme config is used, it would need fetching like in main script.js
                // For simplicity, this page's theme toggle only handles local localStorage and attribute
            });
        }
        // Apply stored theme preference on load
        const preferredTheme = localStorage.getItem('spectraTheme') || 'dark';
        document.documentElement.setAttribute('data-theme', preferredTheme);

        // Set footer year (moved from inline script)
        if (currentYearElement) {
            currentYearElement.textContent = new Date().getFullYear();
        }
    }

    // --- Header Authentication UI Update ---
    // (Similar to script.js, but targets header elements)
    function updateAuthUI() {
        const token = getAuthToken();
        const username = getUsername();
        const role = getUserRole(); // Get role

        if (token && username) {
            if(loginLinkHeader) loginLinkHeader.style.display = 'none';
            if(registerLinkHeader) registerLinkHeader.style.display = 'none';
            if(logoutLinkHeader) logoutLinkHeader.style.display = 'inline-block';
            if(userInfoHeaderDisplay) userInfoHeaderDisplay.style.display = 'inline';
            if(usernameDisplayHeader) usernameDisplayHeader.textContent = `${username} (${role || 'user'})`; // Display role
        } else {
            if(loginLinkHeader) loginLinkHeader.style.display = 'inline-block';
            if(registerLinkHeader) registerLinkHeader.style.display = 'inline-block';
            if(logoutLinkHeader) logoutLinkHeader.style.display = 'none';
            if(userInfoHeaderDisplay) userInfoHeaderDisplay.style.display = 'none';
            if(usernameDisplayHeader) usernameDisplayHeader.textContent = '';
        }
        // Update comment form visibility based on auth status
        if (getAuthToken()) {
            if (commentForm) commentForm.style.display = 'block';
            const authMessageElement = document.getElementById('authMessagePlaceholder');
            if (authMessageElement) authMessageElement.style.display = 'none';
        } else {
            if (commentForm) commentForm.style.display = 'none';
            const authMessageElement = document.getElementById('authMessagePlaceholder');
            if (authMessageElement) {
                 authMessageElement.innerHTML = 'You must be <a href="login.html">logged in</a> to comment or vote.';
                 authMessageElement.style.display = 'block';
            }
        }
    }

    function handleLogout() {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        localStorage.removeItem('userRole'); // Remove role
        updateAuthUI(); // Update header UI and comment form visibility
        // Also update comment form visibility on this page (already handled in updateAuthUI)
        if (commentForm) commentForm.style.display = 'none';
        const authMessageElement = document.getElementById('authMessagePlaceholder');
        if (authMessageElement) {
            authMessageElement.innerHTML = 'You have been logged out. You must be <a href="login.html">logged in</a> to comment or vote.';
            authMessageElement.style.display = 'block';
        } else {
            const placeholder = document.createElement('p');
            placeholder.id = 'authMessagePlaceholder';
            placeholder.className = 'status-message';
            placeholder.innerHTML = 'You have been logged out. You must be <a href="login.html">logged in</a> to comment or vote.';
            if (commentsListElement) commentsListElement.insertAdjacentElement('afterend', placeholder);
        }
        // No full page reload, just update UI elements on the current page.
        // Or, redirect to home: window.location.href = 'index.html';
    }

    if (logoutLinkHeader) {
        logoutLinkHeader.addEventListener('click', (event) => {
            event.preventDefault();
            handleLogout();
        });
    }

    init();
});
