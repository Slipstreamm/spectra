-- SQL Schema for the Image Board Application

-- Enable UUID generation if not already enabled
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for storing image metadata
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,             -- Original filename or a generated unique name
    filepath VARCHAR(512) NOT NULL UNIQUE,      -- Path to the image file on the server
    mimetype VARCHAR(100),
    filesize INTEGER,                           -- Filesize in bytes
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Consider adding fields like width, height, uploader_id (if users are implemented)
    -- A hash of the file could also be useful for de-duplication:
    -- file_hash VARCHAR(64) UNIQUE -- e.g., SHA256 hash
    CONSTRAINT uq_filepath UNIQUE (filepath) -- Ensure filepath is unique
);

-- Table for storing tags
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    CONSTRAINT uq_tag_name UNIQUE (name) -- Ensure tag names are unique
);

-- Junction table for the many-to-many relationship between images and tags
CREATE TABLE IF NOT EXISTS image_tags (
    image_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (image_id, tag_id),
    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

-- Optional: Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_image_tags_image_id ON image_tags(image_id);
CREATE INDEX IF NOT EXISTS idx_image_tags_tag_id ON image_tags(tag_id);

-- Table for storing user information
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE, -- Added for admin roles
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Optional: Link images to users (if desired in the future)
-- ALTER TABLE images ADD COLUMN uploader_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- Indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

COMMENT ON TABLE images IS 'Stores metadata about uploaded images.';
COMMENT ON COLUMN images.filename IS 'Original or generated filename of the uploaded image.';
COMMENT ON COLUMN images.filepath IS 'Server-side path where the image file is stored.';
COMMENT ON COLUMN images.mimetype IS 'MIME type of the image (e.g., image/jpeg).';
COMMENT ON COLUMN images.filesize IS 'Size of the image file in bytes.';
COMMENT ON COLUMN images.uploaded_at IS 'Timestamp when the image was uploaded.';

COMMENT ON TABLE tags IS 'Stores unique tags that can be applied to images.';
COMMENT ON COLUMN tags.name IS 'The unique name of the tag (e.g., "cat", "landscape").';

COMMENT ON TABLE image_tags IS 'Associates images with tags in a many-to-many relationship.';
COMMENT ON COLUMN image_tags.image_id IS 'Foreign key referencing the ID of the image.';
COMMENT ON COLUMN image_tags.tag_id IS 'Foreign key referencing the ID of the tag.';

COMMENT ON TABLE users IS 'Stores user accounts, including administrators.';
COMMENT ON COLUMN users.username IS 'Unique username for login.';
COMMENT ON COLUMN users.email IS 'Unique email address for the user.';
COMMENT ON COLUMN users.hashed_password IS 'Securely hashed password.';
COMMENT ON COLUMN users.is_active IS 'Whether the user account is active and can log in.';
COMMENT ON COLUMN users.is_superuser IS 'Whether the user has administrator privileges.';
COMMENT ON COLUMN users.created_at IS 'Timestamp when the user account was created.';

-- After running this script, ensure your .env file in the backend directory
-- has the correct POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB.
-- The application will use these to connect.
-- Example:
-- POSTGRES_SERVER=localhost
-- POSTGRES_USER=your_postgres_user
-- POSTGRES_PASSWORD=your_postgres_password
-- POSTGRES_DB=imageboard_db
