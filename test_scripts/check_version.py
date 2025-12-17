"""Check MongoDB version."""
import asyncio
from src.dependencies import AgentDependencies

async def main():
    deps = AgentDependencies()
    await deps.initialize()

    result = await deps.mongo_client.admin.command('buildInfo')
    print(f"MongoDB version: {result.get('version')}")

    await deps.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
