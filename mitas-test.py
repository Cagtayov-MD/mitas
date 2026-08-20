import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            query="Bizim Evin Halleri cast"
        )

        print(result.markdown)

asyncio.run(main())
