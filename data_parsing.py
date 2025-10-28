import re
import os
from environs import Env


def get_question_and_answer():
    env = Env()
    env.read_env()

    file_path = env.str("QUESTIONS_FILE_PATH")

    with open(file_path, "r", encoding="KOI8-R") as my_file:
        file_contents = my_file.read()

    questions = re.findall(r'Вопрос \d+:\s(\D+)\s\sОтвет:', file_contents)
    answers = re.findall(r'Ответ:\s(.+)\s\s', file_contents)
    questions_and_answers = dict(zip(questions, answers))
    return questions_and_answers
