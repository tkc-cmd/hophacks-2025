"""Database initialization script."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from server.persistence import create_tables
from server.config import settings


def main():
    """Initialize the database."""
    print(f"Initializing database at: {settings.database_url}")
    
    try:
        create_tables()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
