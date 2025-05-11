import asyncio
import asyncpg
from getpass import getpass # For securely getting password input
import re # For email validation

# Adjust imports to match your project structure
# Assuming this script is run from the 'backend' directory
from app.core.config import settings
from app.core import security # For password hashing
from app.models import UserCreate # For Pydantic model
# from app.crud import create_user # We'll define a simplified version here or call it

# Simplified email validation
def is_valid_email(email: str) -> bool:
    # Basic regex for email validation
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

async def create_admin_user_in_db(db_pool: asyncpg.Pool, user_in: UserCreate):
    """
    Directly creates a user in the database.
    This is a simplified version of crud.create_user for this script.
    """
    hashed_password = security.get_password_hash(user_in.password)
    
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # Check if email or username already exists
            existing_email = await conn.fetchval("SELECT id FROM users WHERE email = $1", user_in.email)
            if existing_email:
                print(f"Error: User with email {user_in.email} already exists.")
                return None
            
            existing_username = await conn.fetchval("SELECT id FROM users WHERE username = $1", user_in.username)
            if existing_username:
                print(f"Error: User with username {user_in.username} already exists.")
                return None

            query = """
                INSERT INTO users (username, email, hashed_password, is_superuser, is_active)
                VALUES ($1, $2, $3, $4, TRUE)
                RETURNING id, username, email
            """
            user_record = await conn.fetchrow(
                query,
                user_in.username,
                user_in.email,
                hashed_password,
                user_in.is_superuser # Should be True for admin
            )
            return user_record

async def main():
    print("Creating initial admin user...")

    # Get admin user details from input
    while True:
        username = input("Enter admin username (min 3 chars): ").strip()
        if len(username) >= 3:
            break
        print("Username must be at least 3 characters long.")

    while True:
        email = input("Enter admin email: ").strip()
        if is_valid_email(email):
            break
        print("Invalid email format. Please try again.")

    while True:
        password = getpass("Enter admin password (min 8 chars): ")
        if len(password) >= 8:
            password_confirm = getpass("Confirm admin password: ")
            if password == password_confirm:
                break
            else:
                print("Passwords do not match. Please try again.")
        else:
            print("Password must be at least 8 characters long.")

    user_data = UserCreate(
        username=username,
        email=email,
        password=password,
        is_superuser=True # Ensure this admin is a superuser
    )

    db_pool = None
    try:
        # Establish a database connection pool
        # Ensure DATABASE_URL is correctly formed in your settings
        db_pool = await asyncpg.create_pool(str(settings.DATABASE_URL))
        print("Database connection pool established.")

        created_user = await create_admin_user_in_db(db_pool, user_data)

        if created_user:
            print(f"Admin user '{created_user['username']}' with email '{created_user['email']}' created successfully!")
        else:
            print("Failed to create admin user. Check logs or previous error messages.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if db_pool:
            await db_pool.close()
            print("Database connection pool closed.")

if __name__ == "__main__":
    # Ensure your database schema (users table) is created before running this.
    # You can run this script from the 'backend' directory:
    # python create_initial_admin.py
    asyncio.run(main())
