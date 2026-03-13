import os

_raw_url = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.erjxlphndhkpdfmglzyv:v2TCYGJ2noIUgtYu@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
)

# Supabase requires SSL — append sslmode=require if not already present
if "sslmode" not in _raw_url:
    sep = "&" if "?" in _raw_url else "?"
    DATABASE_URL = _raw_url + sep + "sslmode=require"
else:
    DATABASE_URL = _raw_url
