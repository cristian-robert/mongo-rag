"""Check MongoDB Atlas cluster information."""

import asyncio
from src.dependencies import AgentDependencies

async def main():
    deps = AgentDependencies()
    await deps.initialize()

    print("="*80)
    print("MongoDB Atlas Cluster Information")
    print("="*80)

    # Get build info
    build_info = await deps.mongo_client.admin.command('buildInfo')
    print(f"\nMongoDB Version: {build_info.get('version')}")
    print(f"Git Version: {build_info.get('gitVersion', 'N/A')}")

    # Get server status (includes tier info)
    try:
        server_status = await deps.mongo_client.admin.command('serverStatus')
        print(f"\nCluster Type: {server_status.get('process', 'N/A')}")
    except Exception as e:
        print(f"\nCouldn't get server status: {e}")

    # Check connection string for tier hints
    print(f"\nConnection String: {deps.settings.mongodb_uri.split('@')[1] if '@' in deps.settings.mongodb_uri else 'N/A'}")

    print("\n" + "="*80)
    print("IMPORTANT: $rankFusion Requirements")
    print("="*80)
    print("\n$rankFusion is a PREVIEW feature that requires:")
    print("  1. MongoDB 8.0+ (You have: {})".format(build_info.get('version')))
    print("  2. Atlas cluster tier M10 or higher (M0/M2/M5 may not support it)")
    print("  3. Both vector_index (Vector Search) AND text_index (Atlas Search)")
    print("  4. Preview features may need to be explicitly enabled in Atlas")

    print("\nIf you're on M0/M2/M5 (free/shared tier):")
    print("  - Upgrade to M10+ dedicated cluster")
    print("  - Or use the manual hybrid search fallback")

    print("\nIf you're on M10+:")
    print("  - Check Atlas UI > Project Settings > Preview Features")
    print("  - Ensure 'Hybrid Search' or '$rankFusion' is enabled")

    await deps.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
