from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID, CHANNEL_ID
from services import upload_photo_to_telegraph, append_tour_to_sheet

router = Router()

# Ограничиваем доступ только для админа
# router.message.filter(F.from_user.id == ADMIN_ID)
# router.callback_query.filter(F.from_user.id == ADMIN_ID)

class TourFSM(StatesGroup):
    waiting_for_name = State()
    waiting_for_location = State()
    waiting_for_details = State()
    waiting_for_price = State()
    waiting_for_photo = State()

def get_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Опубликовать", callback_data="publish_tour"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_tour")
            ]
        ]
    )

def format_post_text(data: dict) -> str:
    return (
        f"🔥 <b>ГОРЯЩИЙ ТУР: {data['name']}</b>\n\n"
        f"📍 <b>Локация:</b> {data['location']}\n"
        f"ℹ️ <b>Детали:</b> {data['details']}\n"
        f"💰 <b>Цена:</b> {data['price']}\n\n"
        f"<i>Для бронирования обращайтесь к менеджеру!</i>"
    )

@router.message(Command("add_tour"))
async def cmd_add_tour(message: Message, state: FSMContext):
    await message.answer("Начинаем создание поста. Введи <b>название отеля/тура</b>:", parse_mode="HTML")
    await state.set_state(TourFSM.waiting_for_name)

@router.message(TourFSM.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Отлично. Теперь введи <b>локацию (страна, курорт)</b>:", parse_mode="HTML")
    await state.set_state(TourFSM.waiting_for_location)

@router.message(TourFSM.waiting_for_location, F.text)
async def process_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Введи <b>детали</b> (например: 7 ночей, всё включено, перелет включен):", parse_mode="HTML")
    await state.set_state(TourFSM.waiting_for_details)

@router.message(TourFSM.waiting_for_details, F.text)
async def process_details(message: Message, state: FSMContext):
    await state.update_data(details=message.text)
    await message.answer("Введи <b>цену</b> (например: 120 000 руб. за двоих):", parse_mode="HTML")
    await state.set_state(TourFSM.waiting_for_price)

@router.message(TourFSM.waiting_for_price, F.text)
async def process_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Остался последний шаг. <b>Отправь фотографию</b> для поста:", parse_mode="HTML")
    await state.set_state(TourFSM.waiting_for_photo)

@router.message(TourFSM.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot):
    processing_msg = await message.answer("⏳ Загружаю фото и формирую пост...")
    
    # Скачиваем фото в память
    photo_file = await bot.get_file(message.photo[-1].file_id)
    downloaded_file = await bot.download_file(photo_file.file_path)
    file_bytes = downloaded_file.read()
    
    try:
        # Загружаем на Telegraph
        photo_url = await upload_photo_to_telegraph(file_bytes)
    except Exception as e:
        await processing_msg.edit_text(f"❌ Ошибка загрузки фото: {e}")
        return

    await state.update_data(photo_url=photo_url)
    data = await state.get_data()
    
    # Предпросмотр поста
    post_text = format_post_text(data)
    await processing_msg.delete()
    await message.answer_photo(
        photo=message.photo[-1].file_id,
        caption=f"<b>ПРЕДПРОСМОТР ПОСТА:</b>\n\n{post_text}",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard()
    )

@router.callback_query(F.data == "publish_tour")
async def process_publish(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not data:
        await callback.message.edit_caption(caption="❌ Данные устарели. Начни заново через /add_tour.")
        return

    post_text = format_post_text(data)
    
    try:
        # 1. Отправляем в канал
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=data['photo_url'],
            caption=post_text,
            parse_mode="HTML"
        )
        
        # 2. Сохраняляем в Google Таблицу (строка с данными)
        row = [
            data.get('name'), 
            data.get('location'), 
            data.get('details'), 
            data.get('price'), 
            data.get('photo_url')
        ]
        await append_tour_to_sheet(row)
        
        await callback.message.edit_caption(caption="✅ Пост успешно опубликован в канал и сохранен в таблицу!")
        await state.clear()
        
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "cancel_tour")
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_caption(caption="❌ Публикация отменена.")