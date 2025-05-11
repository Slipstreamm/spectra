-- SQL Schema for the Image Board Application

-- Enable UUID generation if not already enabled
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for storing post metadata (renamed from images)
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,             -- Original filename or a generated unique name for the image
    filepath VARCHAR(512) NOT NULL UNIQUE,      -- Path to the image file on the server
    mimetype VARCHAR(100),
    filesize INTEGER,                           -- Filesize in bytes
    title VARCHAR(255) DEFAULT NULL,            -- Optional title for the post
    description TEXT DEFAULT NULL,              -- Optional description for the post
    uploader_id INTEGER REFERENCES users(id) ON DELETE SET NULL, -- Link to the user who uploaded
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Consider adding fields like width, height
    -- A hash of the file could also be useful for de-duplication:
    -- file_hash VARCHAR(64) UNIQUE -- e.g., SHA256 hash
    CONSTRAINT uq_filepath_posts UNIQUE (filepath) -- Ensure filepath is unique
);

-- Table for storing tags
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    CONSTRAINT uq_tag_name UNIQUE (name) -- Ensure tag names are unique
);

-- Junction table for the many-to-many relationship between posts and tags (renamed from image_tags)
CREATE TABLE IF NOT EXISTS post_tags (
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

-- Table for storing user information
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing comments on posts
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, -- User who made the comment, NULL if user is deleted
    parent_comment_id INTEGER REFERENCES comments(id) ON DELETE CASCADE, -- For threaded replies
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing votes on posts and comments
CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    comment_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    vote_type SMALLINT NOT NULL CHECK (vote_type IN (-1, 1)), -- -1 for downvote, 1 for upvote
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_vote_target UNIQUE (user_id, post_id, comment_id), -- User can vote once per target
    CONSTRAINT chk_vote_target CHECK (
        (post_id IS NOT NULL AND comment_id IS NULL) OR
        (post_id IS NULL AND comment_id IS NOT NULL)
    ) -- Ensures a vote is for either a post or a comment, not both or neither
);


-- Optional: Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_post_tags_post_id ON post_tags(post_id);
CREATE INDEX IF NOT EXISTS idx_post_tags_tag_id ON post_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_comments_user_id ON comments(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_parent_comment_id ON comments(parent_comment_id);
CREATE INDEX IF NOT EXISTS idx_votes_user_id ON votes(user_id);
CREATE INDEX IF NOT EXISTS idx_votes_post_id ON votes(post_id);
CREATE INDEX IF NOT EXISTS idx_votes_comment_id ON votes(comment_id);


-- Comments on tables and columns
COMMENT ON TABLE posts IS 'Stores metadata about uploaded posts, including their associated image.';
COMMENT ON COLUMN posts.filename IS 'Original or generated filename of the uploaded image for the post.';
COMMENT ON COLUMN posts.filepath IS 'Server-side path where the image file for the post is stored.';
COMMENT ON COLUMN posts.mimetype IS 'MIME type of the image (e.g., image/jpeg).';
COMMENT ON COLUMN posts.filesize IS 'Size of the image file in bytes.';
COMMENT ON COLUMN posts.title IS 'Optional title for the post.';
COMMENT ON COLUMN posts.description IS 'Optional description for the post.';
COMMENT ON COLUMN posts.uploader_id IS 'Foreign key referencing the user who uploaded the post.';
COMMENT ON COLUMN posts.uploaded_at IS 'Timestamp when the post (and its image) was uploaded.';

COMMENT ON TABLE tags IS 'Stores unique tags that can be applied to posts.';
COMMENT ON COLUMN tags.name IS 'The unique name of the tag (e.g., "cat", "landscape").';

COMMENT ON TABLE post_tags IS 'Associates posts with tags in a many-to-many relationship.';
COMMENT ON COLUMN post_tags.post_id IS 'Foreign key referencing the ID of the post.';
COMMENT ON COLUMN post_tags.tag_id IS 'Foreign key referencing the ID of the tag.';

COMMENT ON TABLE users IS 'Stores user accounts, including administrators.';
COMMENT ON COLUMN users.username IS 'Unique username for login.';
COMMENT ON COLUMN users.email IS 'Unique email address for the user.';
COMMENT ON COLUMN users.hashed_password IS 'Securely hashed password.';
COMMENT ON COLUMN users.is_active IS 'Whether the user account is active and can log in.';
COMMENT ON COLUMN users.is_superuser IS 'Whether the user has administrator privileges.';
COMMENT ON COLUMN users.created_at IS 'Timestamp when the user account was created.';

COMMENT ON TABLE comments IS 'Stores comments made on posts.';
COMMENT ON COLUMN comments.post_id IS 'Foreign key referencing the post the comment belongs to.';
COMMENT ON COLUMN comments.user_id IS 'Foreign key referencing the user who made the comment.';
COMMENT ON COLUMN comments.parent_comment_id IS 'Foreign key for threaded replies, referencing another comment.';
COMMENT ON COLUMN comments.content IS 'The text content of the comment.';
COMMENT ON COLUMN comments.created_at IS 'Timestamp when the comment was created.';
COMMENT ON COLUMN comments.updated_at IS 'Timestamp when the comment was last updated.';

COMMENT ON TABLE votes IS 'Stores user votes on posts and comments.';
COMMENT ON COLUMN votes.user_id IS 'Foreign key referencing the user who cast the vote.';
COMMENT ON COLUMN votes.post_id IS 'Foreign key referencing the post being voted on (if applicable).';
COMMENT ON COLUMN votes.comment_id IS 'Foreign key referencing the comment being voted on (if applicable).';
COMMENT ON COLUMN votes.vote_type IS 'Type of vote: 1 for upvote, -1 for downvote.';
COMMENT ON COLUMN votes.created_at IS 'Timestamp when the vote was cast.';


-- After running this script, ensure your .env file in the backend directory
-- has the correct POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB.
-- The application will use these to connect.
-- Example:
-- POSTGRES_SERVER=localhost
-- POSTGRES_USER=your_postgres_user
-- POSTGRES_PASSWORD=your_postgres_password
-- POSTGRES_DB=imageboard_db
