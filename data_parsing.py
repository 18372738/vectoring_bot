import re


def get_question_and_answer():
    with open("1.txt", "r", encoding="KOI8-R") as my_file:
        file_contents = my_file.read()

    questions = re.findall(r'Вопрос \d+:\s(\D+)\s\sОтвет:', file_contents)
    answers = re.findall(r'Ответ:\s(.+)\s\s', file_contents)
    dict_for_vectoring = dict(zip(questions, answers))
    return dict_for_vectoring

get_question_and_answer()
