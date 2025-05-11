import asyncpg
import redis.asyncio as redis_async
import json
from typing import List, Dict, Any, Optional
from . import models
from .core.config import settings
from .core import security

# Helper function to robustly parse tags
def _parse_tags_from_source(tags_source: Any) -> List[models.Tag]:
    actual_tag_data_list = []
    if isinstance(tags_source, str):
        try:
            parsed_json = json.loads(tags_source)
            if isinstance(parsed_json, list):
                actual_tag_data_list = parsed_json
            else:
                print(f"Warning: Tags source string did not parse to a list: {str(tags_source)[:100]}")
        except json.JSONDecodeError:
            print(f"Warning: JSONDecodeError for tags source string: {str(tags_source)[:100]}")
    elif isinstance(tags_source, list):
        actual_tag_data_list = tags_source
    else:
        if tags_source is not None:
            print(f"Warning: Tags source is neither string nor list: {type(tags_source)}")

    parsed_tags = []
    for item in actual_tag_data_list:
        item_dict = None
        if isinstance(item, dict):
            item_dict = item
        elif isinstance(item, str):
            try:
                loaded_item = json.loads(item)
                if isinstance(loaded_item, dict):
                    item_dict = loaded_item
                else:
                    print(f"Warning: Tag item string did not parse to a dict: {item[:100]}")
            except json.JSONDecodeError:
                print(f"Warning: JSONDecodeError for tag item string: {item[:100]}")
        
        if item_dict:
            try:
                if 'id' in item_dict and isinstance(item_dict['id'], int) and \
                   'name' in item_dict and isinstance(item_dict['name'], str):
                    parsed_tags.append(models.Tag(**item_dict))
                else:
                    print(f"Warning: Tag item dict is missing fields or has wrong types: {item_dict}")
            except Exception as e:
                print(f"Warning: Failed to create Tag from dict {item_dict}. Error: {e}")
        else:
            if item is not None:
                 print(f"Warning: Item in tags list is not a dict or valid JSON string for a dict: {type(item)} - {str(item)[:100]}")
    return parsed_tags

# Cache constants
POST_CACHE_PREFIX = "post:"
POST_LIST_CACHE_PREFIX = "posts_list:"
POST_COUNT_CACHE_PREFIX = "posts_count:"
CACHE_EXPIRY_SECONDS = 300 # 5 minutes

async def get_or_create_tag(db: asyncpg.Connection, tag_name: str) -> models.Tag:
    tag_name_cleaned = tag_name.strip().lower().replace(' ', '_')
    if not tag_name_cleaned:
        raise ValueError("Tag name cannot be empty.")
    async with db.transaction():
        tag_record = await db.fetchrow("SELECT id, name FROM tags WHERE name = $1", tag_name_cleaned)
        if tag_record:
            return models.Tag(id=tag_record['id'], name=tag_record['name'])
        created_tag_record = await db.fetchrow(
            "INSERT INTO tags (name) VALUES ($1) RETURNING id, name", tag_name_cleaned
        )
        if not created_tag_record:
            raise Exception(f"Failed to create tag: {tag_name_cleaned}")
        return models.Tag(id=created_tag_record['id'], name=created_tag_record['name'])

async def create_post_with_tags(
    db: asyncpg.Connection,
    redis: redis_async.Redis,
    post_data: models.PostCreate,
    filepath_on_disk: str,
    uploader_id: int
) -> models.Post:
    async with db.transaction():
        post_insert_query = """
            INSERT INTO posts (filename, filepath, mimetype, filesize, title, description, uploader_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, filename, filepath, mimetype, filesize, title, description, uploader_id, uploaded_at
        """
        post_record = await db.fetchrow(
            post_insert_query,
            post_data.filename, filepath_on_disk, post_data.mimetype, post_data.filesize,
            post_data.title, post_data.description, uploader_id
        )
        if not post_record:
            raise Exception("Failed to create post record in database.")

        created_post_id = post_record['id']
        processed_tags: List[models.Tag] = []
        if post_data.tags:
            for tag_name in post_data.tags:
                tag_name_cleaned = tag_name.strip().lower()
                if not tag_name_cleaned: continue
                tag_obj = await get_or_create_tag(db, tag_name_cleaned)
                processed_tags.append(tag_obj)
                await db.execute(
                    "INSERT INTO post_tags (post_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    created_post_id, tag_obj.id
                )
        
        uploader_info_record = await db.fetchrow("SELECT * FROM users WHERE id = $1", uploader_id)
        uploader_info = models.User(**uploader_info_record) if uploader_info_record else None
        
        response_post = models.Post(
            id=post_record['id'], filename=post_record['filename'], filepath=post_record['filepath'],
            mimetype=post_record['mimetype'], filesize=post_record['filesize'], title=post_record['title'],
            description=post_record['description'], uploader_id=post_record['uploader_id'],
            uploader=uploader_info, uploaded_at=post_record['uploaded_at'], tags=processed_tags,
            image_url=None, thumbnail_url=None, comment_count=0, upvotes=0, downvotes=0
        )
        
        list_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_LIST_CACHE_PREFIX}*")]
        if list_cache_keys: await redis.delete(*list_cache_keys)
        count_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_COUNT_CACHE_PREFIX}*")]
        if count_cache_keys: await redis.delete(*count_cache_keys)
        return response_post

async def get_post(db: asyncpg.Connection, redis: redis_async.Redis, post_id: int) -> Optional[models.Post]:
    cache_key = f"{POST_CACHE_PREFIX}{post_id}"
    cached_post_json = await redis.get(cache_key)
    if cached_post_json:
        try:
            post_dict = json.loads(cached_post_json)
            post_dict['tags'] = _parse_tags_from_source(post_dict.get('tags', []))
            if post_dict.get('uploader') and isinstance(post_dict['uploader'], dict):
                 post_dict['uploader'] = models.User(**post_dict['uploader'])
            return models.Post(**post_dict)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error decoding/parsing cached post for ID: {post_id}. Error: {e}. Fetching from DB.")

    query = """
        SELECT
            p.id, p.filename, p.filepath, p.mimetype, p.filesize, p.title, p.description,
            p.uploaded_at, p.uploader_id,
            u.username AS uploader_username, u.email AS uploader_email, u.is_active AS uploader_is_active,
            u.is_superuser AS uploader_is_superuser, u.created_at AS uploader_created_at,
            COALESCE((SELECT json_agg(json_build_object('id', t.id, 'name', t.name) ORDER BY t.name)
                      FROM tags t JOIN post_tags pt ON t.id = pt.tag_id WHERE pt.post_id = p.id), '[]'::json) AS tags,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = 1) AS upvotes,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = -1) AS downvotes
        FROM posts p
        LEFT JOIN users u ON p.uploader_id = u.id
        WHERE p.id = $1;
    """
    post_record = await db.fetchrow(query, post_id)
    if not post_record: return None

    parsed_db_tags = _parse_tags_from_source(post_record['tags'])
    uploader_data = None
    if post_record['uploader_id']:
        uploader_data = models.User(
            id=post_record['uploader_id'], username=post_record['uploader_username'], email=post_record['uploader_email'],
            is_active=post_record['uploader_is_active'], is_superuser=post_record['uploader_is_superuser'],
            created_at=post_record['uploader_created_at']
        )
    db_post_model = models.Post(
        id=post_record['id'], filename=post_record['filename'], filepath=post_record['filepath'],
        mimetype=post_record['mimetype'], filesize=post_record['filesize'], title=post_record['title'],
        description=post_record['description'], uploaded_at=post_record['uploaded_at'],
        uploader_id=post_record['uploader_id'], uploader=uploader_data, tags=parsed_db_tags,
        image_url=None, thumbnail_url=None, comment_count=post_record['comment_count'],
        upvotes=post_record['upvotes'], downvotes=post_record['downvotes']
    )
    await redis.set(cache_key, db_post_model.model_dump_json(), ex=CACHE_EXPIRY_SECONDS)
    return db_post_model

async def get_posts(
    db: asyncpg.Connection, redis: redis_async.Redis, skip: int = 0, limit: int = 10,
    tags_filter: Optional[List[str]] = None
) -> List[models.Post]:
    normalized_tags_key_part = "_".join(sorted([tag.strip().lower().replace(' ', '_') for tag in tags_filter])) if tags_filter else "all"
    cache_key = f"{POST_LIST_CACHE_PREFIX}skip_{skip}_limit_{limit}_tags_{normalized_tags_key_part}"
    cached_posts_json = await redis.get(cache_key)
    if cached_posts_json:
        try:
            posts_dict_list = json.loads(cached_posts_json)
            response_posts = []
            for post_dict in posts_dict_list:
                post_dict['tags'] = _parse_tags_from_source(post_dict.get('tags', []))
                if post_dict.get('uploader') and isinstance(post_dict['uploader'], dict):
                    post_dict['uploader'] = models.User(**post_dict['uploader'])
                response_posts.append(models.Post(**post_dict))
            return response_posts
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error decoding/parsing cached post list for key: {cache_key}. Error: {e}. Fetching from DB.")

    base_query = """
        SELECT
            p.id, p.filename, p.filepath, p.mimetype, p.filesize, p.title, p.description,
            p.uploaded_at, p.uploader_id,
            u.username AS uploader_username, u.email AS uploader_email, u.is_active AS uploader_is_active,
            u.is_superuser AS uploader_is_superuser, u.created_at AS uploader_created_at,
            COALESCE((SELECT json_agg(json_build_object('id', t.id, 'name', t.name) ORDER BY t.name)
                      FROM tags t JOIN post_tags pt ON t.id = pt.tag_id WHERE pt.post_id = p.id), '[]'::json) AS tags,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = 1) AS upvotes,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = -1) AS downvotes
        FROM posts p
        LEFT JOIN users u ON p.uploader_id = u.id
    """
    conditions = []
    query_params: List[Any] = []
    param_idx = 1
    if tags_filter:
        normalized_tags_filter = [tag.strip().lower().replace(' ', '_') for tag in tags_filter if tag.strip()]
        if normalized_tags_filter:
            tag_placeholders = ', '.join([f'${i+param_idx}' for i in range(len(normalized_tags_filter))])
            conditions.append(f"""
                (SELECT COUNT(DISTINCT t_filter.id)
                 FROM post_tags pt_filter JOIN tags t_filter ON pt_filter.tag_id = t_filter.id
                 WHERE pt_filter.post_id = p.id AND t_filter.name IN ({tag_placeholders})) = {len(normalized_tags_filter)}
            """)
            query_params.extend(normalized_tags_filter)
            param_idx += len(normalized_tags_filter)
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)
    base_query += f" ORDER BY p.uploaded_at DESC, p.id DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    query_params.extend([limit, skip])

    post_records = await db.fetch(base_query, *query_params)
    posts_list = []
    for record in post_records:
        parsed_db_tags = _parse_tags_from_source(record['tags'])
        uploader_data = None
        if record['uploader_id']:
            uploader_data = models.User(
                id=record['uploader_id'], username=record['uploader_username'], email=record['uploader_email'],
                is_active=record['uploader_is_active'], is_superuser=record['uploader_is_superuser'],
                created_at=record['uploader_created_at']
            )
        posts_list.append(models.Post(
            id=record['id'], filename=record['filename'], filepath=record['filepath'],
            mimetype=record['mimetype'], filesize=record['filesize'], title=record['title'],
            description=record['description'], uploaded_at=record['uploaded_at'],
            uploader_id=record['uploader_id'], uploader=uploader_data, tags=parsed_db_tags,
            image_url=None, thumbnail_url=None, comment_count=record['comment_count'],
            upvotes=record['upvotes'], downvotes=record['downvotes']
        ))
    if posts_list:
        try:
            cacheable_data = json.dumps([post.model_dump() for post in posts_list])
            await redis.set(cache_key, cacheable_data, ex=CACHE_EXPIRY_SECONDS)
        except Exception as e:
            print(f"Error caching post list: {e}")
    return posts_list

async def count_posts(
    db: asyncpg.Connection, redis: redis_async.Redis, tags_filter: Optional[List[str]] = None
) -> int:
    normalized_tags_key_part = "_".join(sorted([tag.strip().lower().replace(' ', '_') for tag in tags_filter])) if tags_filter else "all"
    cache_key = f"{POST_COUNT_CACHE_PREFIX}tags_{normalized_tags_key_part}"
    cached_count = await redis.get(cache_key)
    if cached_count is not None:
        try: return int(cached_count)
        except ValueError: print(f"Error decoding cached post count for key: {cache_key}. Fetching from DB.")

    base_query = "SELECT COUNT(DISTINCT p.id) FROM posts p"
    conditions = []
    query_params: List[Any] = []
    param_idx = 1
    if tags_filter:
        normalized_tags_filter = [tag.strip().lower().replace(' ', '_') for tag in tags_filter if tag.strip()]
        if normalized_tags_filter:
            tag_placeholders = ', '.join([f'${i+param_idx}' for i in range(len(normalized_tags_filter))])
            # This join is needed to filter by tags
            # Ensure the FROM clause includes necessary joins if conditions depend on them
            # For tag filtering, we need to join with post_tags and tags
            from_clause_with_joins = """
                FROM posts p
                JOIN post_tags pt_count ON p.id = pt_count.post_id
                JOIN tags t_count ON pt_count.tag_id = t_count.id
            """
            if "FROM posts p" in base_query and "JOIN" not in conditions_to_str(conditions): # Avoid duplicate joins if already added
                 base_query = base_query.replace("FROM posts p", from_clause_with_joins)
            elif "FROM posts p" not in base_query: # If base_query was already complex
                 # This case needs careful handling; for now, assume base_query starts simple
                 pass


            conditions.append(f"""
                (SELECT COUNT(DISTINCT t_inner.id)
                 FROM post_tags pt_inner JOIN tags t_inner ON pt_inner.tag_id = t_inner.id
                 WHERE pt_inner.post_id = p.id AND t_inner.name IN ({tag_placeholders})) = {len(normalized_tags_filter)}
            """)
            query_params.extend(normalized_tags_filter)
    
    if conditions:
        # If tags_filter was applied, the base_query might have been changed to include joins.
        # If not, and conditions exist, ensure joins are present for tag filtering.
        # This logic is a bit complex; the key is that the final query must be valid.
        # A simpler way for count:
        if tags_filter and normalized_tags_filter: # Re-check for clarity
            # Construct a query that correctly counts posts matching all tags
            count_query = """
                SELECT COUNT(p.id)
                FROM posts p
                WHERE EXISTS (
                    SELECT 1
                    FROM post_tags pt
                    JOIN tags t ON pt.tag_id = t.id
                    WHERE pt.post_id = p.id AND t.name IN ({})
                    GROUP BY pt.post_id
                    HAVING COUNT(DISTINCT t.id) = {}
                );
            """.format(
                ', '.join([f'${i+1}' for i in range(len(normalized_tags_filter))]),
                len(normalized_tags_filter)
            )
            final_query_params = normalized_tags_filter
            # If there were other conditions, this simplified query would need to incorporate them.
            # For now, assuming tags_filter is the only complex filter for count.
            # If other filters were simple (e.g., on posts.title), they'd be added to this WHERE clause.
            # This example prioritizes correct "all tags" matching for count.
            base_query = count_query # Override base_query if tag filtering is active
            query_params = final_query_params # Override query_params
        elif conditions: # Other conditions, but not the complex tag filter
             base_query += " WHERE " + " AND ".join(conditions)
        # If no conditions, base_query = "SELECT COUNT(DISTINCT p.id) FROM posts p" is fine.

    count_record = await db.fetchval(base_query, *query_params)
    db_count = count_record if count_record is not None else 0
    await redis.set(cache_key, db_count, ex=CACHE_EXPIRY_SECONDS)
    return db_count

# Helper for count_posts query construction (internal)
def conditions_to_str(conditions: List[str]) -> str:
    return " AND ".join(conditions)


# User CRUD operations
async def get_user_by_email(db: asyncpg.Connection, email: str) -> Optional[models.UserInDB]:
    query = "SELECT id, username, email, hashed_password, is_active, is_superuser, created_at FROM users WHERE email = $1"
    user_record = await db.fetchrow(query, email)
    if user_record: return models.UserInDB(**user_record)
    return None

async def get_user_by_username(db: asyncpg.Connection, username: str) -> Optional[models.UserInDB]:
    query = "SELECT id, username, email, hashed_password, is_active, is_superuser, created_at FROM users WHERE username = $1"
    user_record = await db.fetchrow(query, username)
    if user_record: return models.UserInDB(**user_record)
    return None

async def create_user(db: asyncpg.Connection, user_in: models.UserCreate) -> models.User:
    hashed_password = security.get_password_hash(user_in.password)
    existing_email_user = await get_user_by_email(db, user_in.email)
    if existing_email_user: raise ValueError(f"User with email {user_in.email} already exists.")
    existing_username_user = await get_user_by_username(db, user_in.username)
    if existing_username_user: raise ValueError(f"User with username {user_in.username} already exists.")
    query = """
        INSERT INTO users (username, email, hashed_password, is_superuser, is_active)
        VALUES ($1, $2, $3, $4, TRUE)
        RETURNING id, username, email, is_active, is_superuser, created_at
    """
    user_record = await db.fetchrow(
        query, user_in.username, user_in.email, hashed_password, user_in.is_superuser
    )
    if not user_record: raise Exception("Failed to create user.")
    return models.User(**user_record)

async def get_user(db: asyncpg.Connection, user_id: int) -> Optional[models.UserInDB]: # Should return UserInDB for internal use
    query = "SELECT id, username, email, hashed_password, is_active, is_superuser, created_at FROM users WHERE id = $1"
    user_record = await db.fetchrow(query, user_id)
    if user_record:
        return models.UserInDB(**user_record) # Return UserInDB as it contains hashed_password
    return None

# Comment CRUD operations
COMMENTS_FOR_POST_CACHE_PREFIX = "comments_for_post:"

async def create_comment(db: asyncpg.Connection, redis: redis_async.Redis, comment_data: models.CommentCreate, post_id: int, user_id: int) -> models.Comment:
    async with db.transaction():
        # Insert the comment
        query = """
            INSERT INTO comments (post_id, user_id, parent_comment_id, content)
            VALUES ($1, $2, $3, $4)
            RETURNING id, post_id, user_id, parent_comment_id, content, created_at, updated_at
        """
        comment_record = await db.fetchrow(
            query,
            post_id,
            user_id,
            comment_data.parent_comment_id,
            comment_data.content
        )
        if not comment_record:
            raise Exception("Failed to create comment.")

        # Fetch the user who made the comment
        commenter_user = await get_user(db, user_id) # get_user returns UserInDB
        if not commenter_user:
            # This should ideally not happen if user_id is valid
            raise Exception("Commenter user not found.")

        # Invalidate post cache as comment_count has changed
        await redis.delete(f"{POST_CACHE_PREFIX}{post_id}")
        # Potentially invalidate post list caches if they show comment counts directly
        # For simplicity, we might rely on TTL or broader invalidation for list caches for now.

        return models.Comment(
            id=comment_record['id'],
            post_id=comment_record['post_id'],
            user_id=comment_record['user_id'],
            user=models.UserBase( # Convert UserInDB to UserBase for embedding
                id=commenter_user.id,
                email=commenter_user.email,
                username=commenter_user.username,
                # is_active and is_superuser are not in UserBase by default in models.Comment
            ),
            parent_comment_id=comment_record['parent_comment_id'],
            content=comment_record['content'],
            created_at=comment_record['created_at'],
            updated_at=comment_record['updated_at'],
            replies=[], # Replies would be fetched separately if needed for deep nesting
            upvotes=0, # Initialize, vote implementation is separate
            downvotes=0 # Initialize
        )

async def get_comments_for_post(db: asyncpg.Connection, redis: redis_async.Redis, post_id: int, skip: int = 0, limit: int = 10) -> List[models.Comment]:
    cache_key = f"{COMMENTS_FOR_POST_CACHE_PREFIX}{post_id}:skip_{skip}:limit_{limit}"
    cached_comments_json = await redis.get(cache_key)

    if cached_comments_json:
        try:
            comments_dict_list = json.loads(cached_comments_json)
            response_comments = []
            for comm_dict in comments_dict_list:
                if comm_dict.get('user') and isinstance(comm_dict['user'], dict):
                    comm_dict['user'] = models.UserBase(**comm_dict['user'])
                # Assuming replies are handled separately or not deeply nested in this call
                comm_dict['replies'] = [] # Placeholder if replies were cached differently
                response_comments.append(models.Comment(**comm_dict))
            print(f"Cache HIT for comments list: {cache_key}")
            return response_comments
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error decoding/parsing cached comments for post {post_id}. Error: {e}. Fetching from DB.")

    query = """
        SELECT
            c.id, c.post_id, c.user_id, c.parent_comment_id, c.content, c.created_at, c.updated_at,
            u.username AS user_username, u.email AS user_email, -- u.is_active, u.is_superuser, u.created_at AS user_created_at,
            (SELECT COUNT(*) FROM votes v WHERE v.comment_id = c.id AND v.vote_type = 1) AS upvotes,
            (SELECT COUNT(*) FROM votes v WHERE v.comment_id = c.id AND v.vote_type = -1) AS downvotes
            -- Replies need to be handled, potentially in a separate query or by recursive CTE if DB supports well
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = $1 AND c.parent_comment_id IS NULL -- Fetch only top-level comments for now
        ORDER BY c.created_at ASC -- Or DESC depending on desired order
        LIMIT $2 OFFSET $3;
    """
    # For threaded comments, the query would be more complex (e.g., recursive CTE)
    # or handled by multiple queries client-side/service-side.
    # This example fetches top-level comments and their direct user info.
    
    comment_records = await db.fetch(query, post_id, limit, skip)
    
    comments_list = []
    for record in comment_records:
        commenter_user_base = models.UserBase(
            # id=record['user_id'], # UserBase doesn't have id by default in models.Comment.user
            email=record['user_email'],
            username=record['user_username']
        )
        comments_list.append(models.Comment(
            id=record['id'],
            post_id=record['post_id'],
            user_id=record['user_id'],
            user=commenter_user_base,
            parent_comment_id=record['parent_comment_id'],
            content=record['content'],
            created_at=record['created_at'],
            updated_at=record['updated_at'],
            replies=[], # Populate if fetching replies recursively
            upvotes=record['upvotes'],
            downvotes=record['downvotes']
        ))

    if comments_list:
        try:
            # For caching, ensure UserBase within Comment is also serializable if not default
            cacheable_data = json.dumps([comment.model_dump() for comment in comments_list])
            await redis.set(cache_key, cacheable_data, ex=CACHE_EXPIRY_SECONDS)
        except Exception as e:
            print(f"Error caching comments list for post {post_id}: {e}")
            
    return comments_list

# Vote CRUD operations
COMMENT_CACHE_PREFIX = "comment:" # For individual comment caching if implemented

async def cast_vote(db: asyncpg.Connection, redis: redis_async.Redis, vote_data: models.VoteCreate, user_id: int) -> Optional[models.Vote]:
    async with db.transaction():
        target_post_id = vote_data.post_id
        target_comment_id = vote_data.comment_id
        new_vote_type = vote_data.vote_type

        # Check for existing vote by this user on this target
        existing_vote_query = """
            SELECT id, vote_type FROM votes
            WHERE user_id = $1 AND post_id = $2 AND comment_id IS NULL
        """
        params = [user_id, target_post_id]
        if target_comment_id:
            existing_vote_query = """
                SELECT id, vote_type FROM votes
                WHERE user_id = $1 AND comment_id = $2 AND post_id IS NULL
            """
            params = [user_id, target_comment_id]
        
        existing_vote_record = await db.fetchrow(existing_vote_query, *params)

        if existing_vote_record:
            # Vote exists
            existing_vote_id = existing_vote_record['id']
            current_vote_type = existing_vote_record['vote_type']
            if current_vote_type == new_vote_type:
                # User clicked the same vote button again - unvote (delete the vote)
                await db.execute("DELETE FROM votes WHERE id = $1", existing_vote_id)
                created_vote_record = None # Vote removed
            else:
                # User changed their vote (e.g., from up to down) - update
                updated_vote_record = await db.fetchrow(
                    "UPDATE votes SET vote_type = $1, created_at = CURRENT_TIMESTAMP WHERE id = $2 RETURNING *",
                    new_vote_type, existing_vote_id
                )
                created_vote_record = updated_vote_record
        else:
            # New vote - insert
            insert_query = """
                INSERT INTO votes (user_id, post_id, comment_id, vote_type)
                VALUES ($1, $2, $3, $4) RETURNING *
            """
            created_vote_record = await db.fetchrow(
                insert_query, user_id, target_post_id, target_comment_id, new_vote_type
            )

        # Invalidate caches
        if target_post_id:
            await redis.delete(f"{POST_CACHE_PREFIX}{target_post_id}")
            # Also invalidate lists where this post might appear with updated vote counts
            # This is a broad invalidation for simplicity.
            list_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_LIST_CACHE_PREFIX}*")]
            if list_cache_keys: await redis.delete(*list_cache_keys)
            count_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_COUNT_CACHE_PREFIX}*")]
            if count_cache_keys: await redis.delete(*count_cache_keys)

        elif target_comment_id:
            # Invalidate specific comment cache (if we implement it)
            # await redis.delete(f"{COMMENT_CACHE_PREFIX}{target_comment_id}")
            # Invalidate the cache for the post this comment belongs to, as its aggregated view might change
            comment_post_id_record = await db.fetchval("SELECT post_id FROM comments WHERE id = $1", target_comment_id)
            if comment_post_id_record:
                await redis.delete(f"{POST_CACHE_PREFIX}{comment_post_id_record}")
                # Also invalidate comment list for that post
                # A more granular approach would be to update the specific comment in the list cache if possible
                comments_list_cache_keys = [key async for key in redis.scan_iter(match=f"{COMMENTS_FOR_POST_CACHE_PREFIX}{comment_post_id_record}:*")]
                if comments_list_cache_keys: await redis.delete(*comments_list_cache_keys)


        if not created_vote_record: # Case where vote was deleted (unvoted)
            return None

        # Fetch user details for the vote response
        voter_user = await get_user(db, created_vote_record['user_id'])
        voter_user_base = models.UserBase(
            email=voter_user.email, 
            username=voter_user.username
        ) if voter_user else None

        return models.Vote(
            id=created_vote_record['id'],
            user_id=created_vote_record['user_id'],
            post_id=created_vote_record['post_id'],
            comment_id=created_vote_record['comment_id'],
            vote_type=created_vote_record['vote_type'],
            created_at=created_vote_record['created_at'],
            user=voter_user_base
        )
