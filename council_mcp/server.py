"""
Council MCP Server
-------------------
Claude Code'dan "ask_council" aracı çağrıldığında, .env dosyasında
API key'i tanımlı olan tüm council üyelerine (Gemini, Qwen, GLM, GPT)
AYNI ANDA soruyu gönderir, cevaplarını toplayıp geri döndürür.

Key'i olmayan bir üye otomatik olarak atlanır - kod değiştirmeye
gerek kalmadan .env'e key eklemek yeterli.
"""

import asyncio
import os

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from providers import gemini, glm, gpt, kimi, minimax, nemotron, qwen

load_dotenv()

server = Server("council")

# Yeni bir council üyesi eklemek için: providers/ altına yeni bir modül
# yaz (aynı is_configured() / ask() arayüzüyle), sonra burada listeye ekle.
COUNCIL_MEMBERS = {
    "gemini": gemini,
    "qwen": qwen,
    "glm": glm,
    "gpt": gpt,
    "kimi": kimi,
    "nemotron": nemotron,
    "minimax": minimax,
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ask_council",
            description=(
                "VİTOS/MİTAS için önemli mimari veya teknik karar noktalarında, "
                "aynı soruyu council'daki (Gemini, Qwen, GLM, GPT, Kimi, "
                "Nemotron, MiniMax - hangileri yapılandırılmışsa) birden fazla modele "
                "paralel sorar ve tüm "
                "cevapları karşılaştırmalı olarak döndürür. Rutin sorularda "
                "DEĞİL, sadece bilinçli olarak ikinci bir görüş istendiğinde "
                "kullanılmalı."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Council'a sorulacak teknik soru",
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "İsteğe bağlı ek bağlam: ilgili kod parçası, "
                            "hata logu, önceki karar gerekçesi vb."
                        ),
                    },
                },
                "required": ["question"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "ask_council":
        raise ValueError(f"Bilinmeyen araç: {name}")

    # .env'i her çağrıda tazele: sunucu çalışırken eklenen/değişen key'ler
    # yeniden başlatma gerektirmeden aktif olsun (2026-07-09, qwen ekleme dersi).
    load_dotenv(override=True)

    question = arguments["question"]
    context = arguments.get("context", "")

    active_members: list[str] = []
    tasks: list[asyncio.Task] = []

    for member_name, module in COUNCIL_MEMBERS.items():
        if module.is_configured():
            active_members.append(member_name)
            tasks.append(asyncio.ensure_future(module.ask(question, context)))

    if not tasks:
        return [
            TextContent(
                type="text",
                text=(
                    "Hiçbir council üyesi için API key tanımlı değil. "
                    ".env dosyasını kontrol et (GEMINI_API_KEY / QWEN_API_KEY / "
                    "GLM_API_KEY / OPENAI_API_KEY)."
                ),
            )
        ]

    responses = await asyncio.gather(*tasks, return_exceptions=True)

    lines = [f"# Council sorusu\n\n{question}\n"]
    if context:
        lines.append(f"**Bağlam:** {context}\n")

    lines.append(f"\n**Yanıt veren üyeler:** {', '.join(active_members)}\n")

    for member_name, response in zip(active_members, responses):
        lines.append(f"\n---\n\n## {member_name}\n")
        if isinstance(response, Exception):
            lines.append(f"HATA: {response}")
        else:
            lines.append(str(response))

    return [TextContent(type="text", text="\n".join(lines))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
