import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.erjxlphndhkpdfmglzyv:v2TCYGJ2noIUgtYu@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
)
