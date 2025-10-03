import logging
import random
import redis
from environs import Env
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

from data_parsing import get_question_and_answer  # Импорт словаря QA

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Клавиатура
keyboard = [
    ['Новый вопрос', 'Сдаться'],
    ['Мой счёт']
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

redis_conn = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

qa_dict = get_question_and_answer()


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Привет! Я бот для викторин!',
        reply_markup=markup
    )


def handle_new_question(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    question = random.choice(list(qa_dict.keys()))
    answer = qa_dict[question]

    redis_conn.set(f"user:{user_id}:question", question)
    redis_conn.set(f"user:{user_id}:answer", answer)

    update.message.reply_text(question)


def handle_give_up(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    answer = redis_conn.get(f"user:{user_id}:answer")

    if answer:
        update.message.reply_text(f"Правильный ответ: {answer}")
    else:
        update.message.reply_text("Нет активного вопроса.")

    redis_conn.delete(f"user:{user_id}:question")
    redis_conn.delete(f"user:{user_id}:answer")


def handle_score(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    score = redis_conn.get(f"user:{user_id}:score") or 0
    update.message.reply_text(f"Ваш счёт: {score}")


def handle_solution_attempt(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_answer = update.message.text.strip().lower()
    correct_answer = redis_conn.get(f"user:{user_id}:answer")

    if not correct_answer:
        update.message.reply_text("Сначала нажмите 'Новый вопрос'.")
        return

    if user_answer == correct_answer.lower():
        update.message.reply_text("Правильно! 🎉")
        redis_conn.incr(f"user:{user_id}:score")
        redis_conn.delete(f"user:{user_id}:question")
        redis_conn.delete(f"user:{user_id}:answer")
    else:
        update.message.reply_text("Неправильно. Попробуйте ещё раз.")


def main():
    env = Env()
    env.read_env()

    telegram_token = env.str("TELEGRAM_TOKEN")

    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.regex("Новый вопрос"), handle_new_question))
    dispatcher.add_handler(MessageHandler(Filters.regex("Сдаться"), handle_give_up))
    dispatcher.add_handler(MessageHandler(Filters.regex("Мой счёт"), handle_score))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_solution_attempt))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
