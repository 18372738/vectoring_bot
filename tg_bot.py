import logging
import random
import redis

from enum import Enum, auto
from environs import Env
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler,)

from data_parsing import get_question_and_answer


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class Quiz(Enum):
    NEW_QUESTION = auto()
    ANSWER = auto()


def start(update: Update, context: CallbackContext) -> Quiz:
    markup = context.bot_data['markup']
    update.message.reply_text(
        'Привет! Я бот для викторин!',
        reply_markup=markup
    )
    return Quiz.NEW_QUESTION


def handle_new_question(update: Update, context: CallbackContext) -> Quiz:
    redis_config = context.bot_data['redis_config']
    question_and_answer = context.bot_data['question_and_answer']
    user_id = update.effective_user.id
    question = random.choice(list(question_and_answer.keys()))
    answer = question_and_answer[question]

    redis_config.set(f"user:{user_id}:question", question)
    redis_config.set(f"user:{user_id}:answer", answer)

    update.message.reply_text(question)
    return Quiz.ANSWER


def handle_solution_attempt(update: Update, context: CallbackContext) -> Quiz:
    redis_config = context.bot_data['redis_config']
    user_id = update.effective_user.id
    user_answer = update.message.text.strip().lower()
    correct_answer = redis_config.get(f"user:{user_id}:answer")

    if not correct_answer:
        update.message.reply_text("Сначала нажмите 'Новый вопрос'.")
        return Quiz.NEW_QUESTION

    if is_correct_answer(user_answer, correct_answer):
        update.message.reply_text("Правильно! 🎉")
        redis_config.incr(f"user:{user_id}:score")
        redis_config.delete(f"user:{user_id}:question")
        redis_config.delete(f"user:{user_id}:answer")
        return Quiz.NEW_QUESTION
    else:
        update.message.reply_text("Неправильно. Попробуйте ещё раз.")
        return Quiz.ANSWER


def handle_give_up(update: Update, context: CallbackContext) -> Quiz:
    redis_config = context.bot_data['redis_config']
    question_and_answer = context.bot_data['question_and_answer']
    user_id = update.effective_user.id
    answer = redis_config.get(f"user:{user_id}:answer")

    if answer:
        update.message.reply_text(f"Правильный ответ: {answer}")
    else:
        update.message.reply_text("Нет активного вопроса.")

    redis_config.delete(f"user:{user_id}:question")
    redis_config.delete(f"user:{user_id}:answer")

    question = random.choice(list(question_and_answer.keys()))
    new_answer = question_and_answer[question]

    redis_config.set(f"user:{user_id}:question", question)
    redis_config.set(f"user:{user_id}:answer", new_answer)

    update.message.reply_text(question)
    return Quiz.ANSWER


def handle_score(update: Update, context: CallbackContext) -> None:
    redis_config = context.bot_data['redis_config']
    user_id = update.effective_user.id
    score = redis_config.get(f"user:{user_id}:score") or 0
    update.message.reply_text(f"Ваш счёт: {score}")


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Вы вышли из викторины.")
    return ConversationHandler.END


def is_correct_answer(user_answer, correct_answer):
    clean_answer = correct_answer.split('.')[0].split('(')[0].strip().lower()
    return clean_answer in user_answer.lower()


def main():
    env = Env()
    env.read_env()
    telegram_token = env.str("TELEGRAM_TOKEN")

    keyboard = [['Новый вопрос', 'Сдаться'], ['Мой счёт']]

    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    redis_config = redis.StrictRedis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True
    )

    question_and_answer = get_question_and_answer()

    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher
    dispatcher.bot_data['markup'] = markup
    dispatcher.bot_data['redis_config'] = redis_config
    dispatcher.bot_data['question_and_answer'] = question_and_answer

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(Filters.text("Мой счёт"), handle_score),
        ],
        states={
            Quiz.NEW_QUESTION: [
                CommandHandler("cancel", cancel),
                MessageHandler(Filters.text("Новый вопрос"), handle_new_question),
                MessageHandler(Filters.text("Мой счёт"), handle_score),
            ],
            Quiz.ANSWER: [
                CommandHandler("cancel", cancel),
                MessageHandler(Filters.text("Мой счёт"), handle_score),
                MessageHandler(Filters.text("Сдаться"), handle_give_up),
                MessageHandler(Filters.text, handle_solution_attempt),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
