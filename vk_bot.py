import random
import redis
from environs import Env

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

from data_parsing import get_question_and_answer


def create_keyboard():
    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)

    keyboard.add_line()
    keyboard.add_button('Мой счёт', color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def start(event, vk):
    vk.messages.send(
        peer_id=event.peer_id,
        random_id=get_random_id(),
        message='Приветствую!\n\nЯ бот для викторин! Чтобы начать, нажмите кнопку "Новый вопрос"',
        keyboard=create_keyboard()
    )


def handle_new_question_request(event, vk, questions, redis_db):
    question = random.choice(list(questions.keys()))
    answer = questions[question].split('.')[0].split('(')[0].strip().lower()

    vk_user_id = f'vk-{event.user_id}'

    redis_db.hset(
        vk_user_id,
        mapping={
            'current_question': question,
            'current_answer': answer,
        },
    )

    vk.messages.send(
        peer_id=event.peer_id,
        random_id=get_random_id(),
        message=question,
        keyboard=create_keyboard()
    )


def update_score(vk_user_id, redis_db):
    score = redis_conn.hget(vk_user_id, 'score')
    score = int(score) if score else 0
    score += 1
    redis_conn.hset(vk_user_id, 'score', score)


def get_score(vk_user_id, redis_db):
    score = redis_db.hget(vk_user_id, 'score')
    return int(score) if score else 0


def handle_score_request(event, vk, redis_db):
    vk_user_id = f'vk-{event.user_id}'
    score = get_score(vk_user_id, redis_db)

    vk.messages.send(
        peer_id=event.peer_id,
        random_id=get_random_id(),
        message=f'Ваш текущий счёт: {score}',
        keyboard=create_keyboard()
    )


def handle_solution_attempt(event, vk, questions, redis_db):
    vk_user_id = f'vk-{event.user_id}'
    user_answer = event.text.lower().strip(' .!?')
    true_answer = redis_db.hget(vk_user_id, 'current_answer')

    if not true_answer:
        vk.messages.send(
            peer_id=event.peer_id,
            random_id=get_random_id(),
            message='Сначала запросите вопрос, нажав кнопку "Новый вопрос".',
            keyboard=create_keyboard(is_question_active=False)
        )
        return

    if user_answer in true_answer.lower():
        update_score(vk_user_id, redis_db)
        vk.messages.send(
            peer_id=event.peer_id,
            random_id=get_random_id(),
            message='Правильно! Для следующего вопроса нажмите "Новый вопрос".',
            keyboard=create_keyboard()
        )

    elif event.text == 'Сдаться':
        vk.messages.send(
            peer_id=event.peer_id,
            random_id=get_random_id(),
            message=f'Правильный ответ: {true_answer}".',
            keyboard=create_keyboard()
        )
        vk.messages.send(
            peer_id=event.peer_id,
            random_id=get_random_id(),
            message=f'{handle_new_question_request(event, vk, questions, redis_db)}',
            keyboard=create_keyboard()
        )

    else:
        vk.messages.send(
            peer_id=event.peer_id,
            random_id=get_random_id(),
            message='Неправильно. Попробуй ещё раз.',
            keyboard=create_keyboard()
        )


def main():

    env = Env()
    env.read_env()

    vk_token = env.str("VK_TOKEN")
    vk_session = vk_api.VkApi(token=vk_token)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    redis_db = redis.StrictRedis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True
    )

    questions = get_question_and_answer()

    print("Бот запущен.")

    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
            continue

        if event.text == 'Начать':
            start(event, vk)
            continue

        if event.text == 'Новый вопрос':
            handle_new_question_request(event, vk, questions, redis_db)
            continue

        if event.text == 'Мой счёт':
            handle_score_request(event, vk, redis_db)
            continue

        handle_solution_attempt(event, vk, questions, redis_db)


if __name__ == '__main__':
    main()
