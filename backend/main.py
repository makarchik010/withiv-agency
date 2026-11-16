import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, ADMIN_ID
from handlers import router
from services import get_tours, get_site_settings, get_reviews

# Разрешаем POST-запросы
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}

async def health_check(request):
    return web.Response(text="Withiv API & Bot are alive!")

async def api_tours(request):
    try:
        tours = await get_tours(only_for_site=True)
        return web.json_response(tours, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)

async def api_reviews(request):
    try:
        reviews = await get_reviews()
        # Преобразуем русские ключи в латинские (которые ожидает фронт)
        formatted_reviews = []
        for r in reviews:
            formatted_reviews.append({
                "name": r.get("Имя", ""),
                "location": r.get("Направление", ""),
                "text": r.get("Текст", "")
            })
        return web.json_response(formatted_reviews, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)

async def api_settings(request):
    try:
        settings = await get_site_settings()
        return web.json_response(settings, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)

# Обязательный обработчик предзапросов (CORS preflight)
async def handle_options(request):
    return web.Response(headers=CORS_HEADERS)

# Эндпоинт для приема заявок с сайта
async def api_lead(request):
    try:
        data = await request.json()
        destination = data.get("destination", "Не указано")
        dates = data.get("dates", "Не указано")
        budget = data.get("budget", "Не указано")
        contact = data.get("contact", "Не указано")
        utm = data.get("utm", "Органика")

        bot = request.app['bot']
        
        text = (
            f"🔥 <b>Новая заявка с сайта!</b>\n\n"
            f"🏝 <b>Запрос:</b> {destination}\n"
            f"📅 <b>Даты/Гости:</b> {dates}\n"
            f"💰 <b>Бюджет:</b> {budget}\n"
            f"📲 <b>Контакт:</b> {contact}\n"
            f"📊 <i>Источник: {utm}</i>"
        )
        
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="HTML")
        
        return web.json_response({"status": "ok"}, headers=CORS_HEADERS)
    except Exception as e:
        logging.error(f"Ошибка при обработке заявки: {e}")
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)

async def start_web_server(bot):
    app = web.Application()
    app['bot'] = bot
    
    app.router.add_get('/', health_check)
    app.router.add_get('/api/tours', api_tours)
    app.router.add_get('/api/reviews', api_reviews)
    app.router.add_get('/api/settings', api_settings)
    
    app.router.add_post('/api/lead', api_lead)
    app.router.add_options('/api/lead', handle_options)
    
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
    
    await start_web_server(bot)
    
    print("Бот и API-сервер успешно запущены!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())