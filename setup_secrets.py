"""
One-time setup script: creates Databricks secret scope and stores API keys
for the AI Restaurant Planner project.

Secrets created:
- restaurant-app/yelp-api-key: Yelp Fusion API key
- restaurant-app/lakebase-url: Lakebase Postgres connection URL

Usage:
    # From notebook or local terminal with Databricks CLI configured
    python setup_secrets.py

Prerequisites:
    - Databricks CLI configured or running in Databricks workspace
    - Yelp API key from https://www.yelp.com/developers
    - Lakebase Postgres connection URL from your workspace

⚠️  SECURITY: Never commit secret values. This script uses getpass for secure input.
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass

def main():
    """Create secret scope and store all required secrets."""
    
    print("=" * 70)
    print("AI Restaurant Planner - Secret Setup")
    print("=" * 70)
    print()
    
    w = WorkspaceClient()
    
    # Create restaurant-app scope
    print("📦 Creating secret scope: restaurant-app...")
    try:
        w.secrets.create_scope(scope="restaurant-app")
        print("✅ Secret scope 'restaurant-app' created")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("ℹ️  Secret scope 'restaurant-app' already exists")
        else:
            raise
    
    print()
    print("-" * 70)
    print("🔑 Enter your secrets (input is hidden)")
    print("-" * 70)
    print()
    
    # 1. Yelp API Key
    print("1️⃣  Yelp Fusion API Key")
    print("   Get from: https://www.yelp.com/developers")
    yelp_key = getpass.getpass("   Paste your Yelp API key: ")
    w.secrets.put_secret(
        scope="restaurant-app",
        key="yelp-api-key",
        string_value=yelp_key
    )
    print("   ✅ Stored: restaurant-app/yelp-api-key")
    print()
    
    # 2. Lakebase Connection URL
    print("2️⃣  Lakebase Postgres Connection URL")
    print("   Example: postgresql://user:pass@ep-xxx-xxx.us-east-1.aws.neon.tech:5432/main?sslmode=require")
    print("   Get from: Lakebase console → Connection Details → Copy URL")
    lakebase_url = getpass.getpass("   Paste your Lakebase URL: ")
    w.secrets.put_secret(
        scope="restaurant-app",
        key="lakebase-url",
        string_value=lakebase_url
    )
    print("   ✅ Stored: restaurant-app/lakebase-url")
    print()
    
    # Set ACLs - allow all users to read
    print("-" * 70)
    print("🔐 Setting permissions...")
    w.secrets.put_acl(
        scope="restaurant-app",
        principal="users",
        permission=workspace.AclPermission.READ,
    )
    print("✅ Granted READ permission to 'users' group")
    print()
    
    print("=" * 70)
    print("✅ Setup Complete!")
    print("=" * 70)
    print()
    print("Secrets stored in scope: restaurant-app")
    print("  • yelp-api-key")
    print("  • lakebase-url")
    print()
    print("Next steps:")
    print("  1. Run SQL files (01-05) in Lakebase to create tables")
    print("  2. Run ingestion notebook to populate restaurant data")
    print("  3. Deploy app: databricks apps deploy app")
    print()

if __name__ == "__main__":
    main()
