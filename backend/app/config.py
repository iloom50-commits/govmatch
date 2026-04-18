import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_raw_url = os.getenv("DATABASE_URL", "")
if not _raw_url:
    raise RuntimeError("DATABASE_URL environment variable is required")

# Supabase requires SSL — append sslmode=require if not already present
if "sslmode" not in _raw_url:
    sep = "&" if "?" in _raw_url else "?"
    DATABASE_URL = _raw_url + sep + "sslmode=require"
else:
    DATABASE_URL = _raw_url
