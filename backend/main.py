import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers import router
from services import get_tours, get_site_settings

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}

async def health_check(request):
    return web.Response(text="Withiv API & Bot are alive!")

async def api_tours(request):
    try:
        # Отдаем только те туры, у которых стоит метка 'both' или 'site'
        tours = await get_tours(only_for_site=True)
        return web.json_response(tours, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)

async def api_settings(request):
    try:
        settings = await get_site_settings()
        return web.json_response(settings, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/api/tours', api_tours)
    app.router.add_get('/api/settings', api_settings)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await start_web_server()
    
    print("Бот и API-сервер успешно запущены!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
