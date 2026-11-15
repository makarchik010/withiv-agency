from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID, CHANNEL_ID
from services import (
    upload_photo_to_telegraph,
    append_tour_to_sheet,
    get_tours,
    delete_tour_from_sheet,
    update_tour_field
)

router = Router()

def is_admin(user_id: int) -> bool:
    return str(user_id) == str(ADMIN_ID)

class AddTourStates(StatesGroup):
    name = State()
    location = State()
    details = State()
    price = State()
    description = State()  # Новый шаг для кастомного текста
    photo = State()

class EditTourStates(StatesGroup):
    waiting_for_value = State()

def format_post_text(data: dict) -> str:
    # Забираем кастомное описание (если оно есть)
    desc = data.get('description') or data.get('Описание') or ""
    
    post = ""
    if desc and str(desc).strip():
        post += f"{str(desc).strip()}\n\n"
        
    post += (
        f"🔥 <b>{data.get('name', data.get('Название'))}</b>\n"
        f"📍 <b>Локация:</b> {data.get('location', data.get('Локация'))}\n"
        f"ℹ️ <b>Детали:</b> {data.get('details', data.get('Детали'))}\n"
        f"💰 <b>Цена:</b> {data.get('price', data.get('Цена'))}\n\n"
        f"<i>Для бронирования обращайтесь к менеджеру!</i>"
    )
    return post

def get_publish_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 В канал и на сайт", callback_data="pub_both")],
            [
                InlineKeyboardButton(text="✈️ Только в канал", callback_data="pub_channel"),
                InlineKeyboardButton(text="🌐 Только на сайт", callback_data="pub_site")
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_tour")]
        ]
    )

# --- СТАРТ И ДОБАВЛЕНИЕ ТУРА ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели управления.")
        return
    await message.answer(
        "👋 Привет! Я панель управления агентством <b>Withiv</b>.\n\n"
        "Доступные команды:\n"
        "➕ /add_tour — Добавить новый тур\n"
        "🗂 /manage — Управление турами (просмотр, редактирование, удаление)",
        parse_mode="HTML"
    )

@router.message(Command("add_tour"))
async def cmd_add_tour(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await state.set_state(AddTourStates.name)
    await message.answer("Начинаем создание тура. Введите <b>название отеля/тура</b>:", parse_mode="HTML")

@router.message(AddTourStates.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddTourStates.location)
    await message.answer("Отлично. Теперь введите <b>локацию</b> (страна, курорт):", parse_mode="HTML")

@router.message(AddTourStates.location)
async def process_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(AddTourStates.details)
    await message.answer("Введите <b>детали</b> (например: 7 ночей, всё включено, перелет):", parse_mode="HTML")

@router.message(AddTourStates.details)
async def process_details(message: Message, state: FSMContext):
    await state.update_data(details=message.text)
    await state.set_state(AddTourStates.price)
    await message.answer("Введите <b>цену</b> (например: 120 000 руб. за двоих):", parse_mode="HTML")

@router.message(AddTourStates.price)
async def process_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(AddTourStates.description)
    await message.answer(
        "📝 <b>Дополнительное описание (Текст поста)</b>\n"
        "Напишите красивое вступление для этого тура. Можно использовать любые эмодзи, абзацы и жирный шрифт — оно появится в самом верху поста в Telegram.\n\n"
        "<i>Если описание не нужно и вы хотите оставить строгий шаблон, просто отправьте минус <code>-</code></i>",
        parse_mode="HTML"
    )

@router.message(AddTourStates.description)
async def process_description(message: Message, state: FSMContext):
    text = message.html_text or ""
    raw_text = message.text or ""
    
    # Если прислали минус, оставляем описание пустым
    if raw_text.strip() == '-':
        desc = ""
    else:
        desc = text
        
    await state.update_data(description=desc)
    await state.set_state(AddTourStates.photo)
    await message.answer("📸 Остался последний шаг. Отправьте <b>фотографию</b> для тура:", parse_mode="HTML")

@router.message(AddTourStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot):
    wait_msg = await message.answer("⏳ Загружаю фото на сервер...")
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        photo_url = await upload_photo_to_telegraph(downloaded_file.read())
        
        await state.update_data(photo_url=photo_url)
        data = await state.get_data()
        
        preview_text = f"<b>ПРЕДПРОСМОТР:</b>\n\n{format_post_text(data)}\n\n<i>Куда публикуем?</i>"
        await wait_msg.delete()
        await message.answer_photo(
            photo=photo_url,
            caption=preview_text,
            reply_markup=get_publish_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка загрузки фото: {str(e)}")

@router.callback_query(F.data == "cancel_tour")
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_caption(caption="❌ Создание тура отменено.")

@router.callback_query(F.data.startswith("pub_"))
async def process_publish(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not data:
        await callback.message.edit_caption(caption="❌ Данные устарели. Начните заново через /add_tour")
        return

    destination = callback.data.split("_")[1]
    post_text = format_post_text(data)
    msg_id = ""
    
    await callback.message.edit_caption(caption="⏳ Публикую...")
    
    try:
        if destination in ['both', 'channel']:
            sent_msg = await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=data.get('photo_url'),
                caption=post_text,
                parse_mode="HTML"
            )
            msg_id = str(sent_msg.message_id)
            
        row = [
            data.get('name'),
            data.get('location'),
            data.get('details'),
            data.get('price'),
            data.get('photo_url'),
            destination,
            msg_id,
            data.get('description', '')  # Сохраняем кастомный текст в столбец H
        ]
        await append_tour_to_sheet(row)

        labels = {
            'both': "✅ Опубликовано в канал и добавлено на сайт!",
            'channel': "✅ Опубликовано только в Telegram-канал!",
            'site': "✅ Добавлено только на сайт!"
        }
        await callback.message.edit_caption(caption=labels[destination])
        await state.clear()

    except Exception as e:
        await callback.message.edit_caption(caption=f"❌ Ошибка при публикации: {str(e)}")

# --- УПРАВЛЕНИЕ СУЩЕСТВУЮЩИМИ ТУРАМИ (/manage) ---

@router.message(Command("manage"))
async def cmd_manage(message: Message):
    if not is_admin(message.from_user.id):
        return
    wait_msg = await message.answer("⏳ Загружаю список туров из базы...")
    try:
        tours = await get_tours(only_for_site=False)
        if not tours:
            await wait_msg.edit_text("📭 В таблице пока нет ни одного тура.")
            return
            
        await wait_msg.delete()
        for t in tours:
            row_idx = t["row_index"]
            dest = t.get("Место публикации", "both")
            dest_icon = "📢 Канал + Сайт" if dest == "both" else ("✈️ Только канал" if dest == "channel" else "🌐 Только сайт")
            
            text = (
                f"<b>{t.get('Название')}</b> ({t.get('Локация')})\n"
                f"💰 Цена: {t.get('Цена')}\n"
                f"ℹ️ Детали: {t.get('Детали')}\n"
                f"📍 Статус: {dest_icon}"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Изм. цену", callback_data=f"edit_4_{row_idx}"),
                    InlineKeyboardButton(text="✏️ Изм. детали", callback_data=f"edit_3_{row_idx}")
                ],
                [InlineKeyboardButton(text="🗑 Удалить везде", callback_data=f"del_{row_idx}")]
            ])
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка чтения таблицы: {str(e)}")

@router.callback_query(F.data.startswith("del_"))
async def process_delete_tour(callback: CallbackQuery, bot: Bot):
    row_idx = int(callback.data.split("_")[1])
    await callback.message.edit_text("⏳ Удаляю тур...")
    try:
        tours = await get_tours(only_for_site=False)
        target_tour = next((t for t in tours if t["row_index"] == row_idx), None)
        
        if target_tour:
            msg_id = str(target_tour.get("ID_поста", "")).strip()
            if msg_id.isdigit():
                try:
                    await bot.delete_message(chat_id=CHANNEL_ID, message_id=int(msg_id))
                except Exception:
                    pass
                    
            await delete_tour_from_sheet(row_idx)
            await callback.message.edit_text("🗑 Тур успешно удален с сайта и из канала!")
        else:
            await callback.message.edit_text("⚠️ Тур не найден (возможно, уже удален).")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка удаления: {str(e)}")

@router.callback_query(F.data.startswith("edit_"))
async def start_edit_tour(callback: CallbackQuery, state: FSMContext):
    _, col_idx, row_idx = callback.data.split("_")
    field_name = "новые детали" if col_idx == "3" else "новую цену"
    
    await state.set_state(EditTourStates.waiting_for_value)
    await state.update_data(edit_col=int(col_idx), edit_row=int(row_idx))
    await callback.message.answer(f"✍️ Введите <b>{field_name}</b> для этого тура:", parse_mode="HTML")
    await callback.answer()

@router.message(EditTourStates.waiting_for_value)
async def finish_edit_tour(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    col_idx = data["edit_col"]
    row_idx = data["edit_row"]
    new_val = message.text
    
    wait_msg = await message.answer("⏳ Обновляю данные...")
    try:
        await update_tour_field(row_idx, col_idx, new_val)
        
        tours = await get_tours(only_for_site=False)
        target_tour = next((t for t in tours if t["row_index"] == row_idx), None)
        
        if target_tour:
            # Подменяем обновленное значение прямо в словаре, чтобы не делать лишний запрос
            if col_idx == 3:
                target_tour["Детали"] = new_val
            elif col_idx == 4:
                target_tour["Цена"] = new_val
                
            msg_id = str(target_tour.get("ID_поста", "")).strip()
            if msg_id.isdigit():
                try:
                    new_caption = format_post_text(target_tour)
                    await bot.edit_message_caption(
                        chat_id=CHANNEL_ID,
                        message_id=int(msg_id),
                        caption=new_caption,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                    
        await wait_msg.edit_text("✅ Данные успешно обновлены на сайте и в канале!")
        await state.clear()
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка обновления: {str(e)}")
