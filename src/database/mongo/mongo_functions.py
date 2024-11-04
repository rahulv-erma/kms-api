import uuid
import datetime

from src import log
from src.database.mongo import mongo_client
from src.database.sql.form_functions import get_form, update_form_postgres
from src.api.api_models.forms import update_survey, update_quiz


def save_survey_submission(
    content: dict,
    form_id: str,
    user_id: str,
) -> str:
    try:
        response_id = str(uuid.uuid4())
        content.update(
            {
                "formId": form_id,
                "userId": user_id,
                "responseId": response_id
            }
        )
        if mongo_client.insert(collection="survey_submissions", content=content):
            return response_id
    except Exception:
        log.exception("Failed ot submit survey")
    return None


def save_quiz_submission(
    content: dict,
    form_id: str,
    user_id: str,
    passing: bool,
    score: float,
    possible_score: float,
    attempts: int = 0
) -> str:
    try:
        response_id = str(uuid.uuid4())
        content.update(
            {
                "formId": form_id,
                "userId": user_id,
                "responseId": response_id,
                "passing": passing,
                "score": score,
                "possibleScore": possible_score,
                "attempt": attempts + 1,
            }
        )
        if mongo_client.insert(collection="quiz_submissions", content=content):
            return response_id
    except Exception:
        log.exception("Failed ot submit quiz")
    return None


async def get_form_from_mongo(type: str = None, id: str = None):
    """function to get a form from mongo

    Args:
        type (str, optional): type of form, quiz or survey. Defaults to "survey".
        id (str, optional): id of form to get. Defaults to None.

    Returns:
        dict: form data from database
    """

    if not id:
        return None

    formSQL = await get_form(type, id)

    if not formSQL:
        return None

    form = mongo_client.find_one(type, {"formId": id})

    if not form:
        return None

    del form["_id"]

    return form


async def update_survey_func(id: str, data: update_survey.Input, user_id: str):
    """Function to update a survey

    Args:
        id (str): Id of the survey to be updated
        data (update_survey.Input): All of the original form data (model) with whatever new needs to be added.

    Returns:
        bool: Returns true if updated, false if failed
    """

    try:
        if not data or not id:
            return None

        query = {"formId": id}
        content = {
            "formName": data.formName,
            "active": data.active,
            "questions": [
                {
                    "questionId": question.questionId,
                    "questionNumber": question.questionNumber,
                    "description": question.description,
                    "answerType": question.answerType,
                    "active": question.active,
                    "choices": [
                        {
                            "answerId": choice.answerId,
                            "description": choice.description,
                            "choicePosition": choice.choicePosition,
                            "active": choice.active,
                        }
                        for choice in question.choices
                    ] if question.choices else []
                }
                for question in data.questions
            ]
        }

        for question in content["questions"]:
            if not question['questionId']:
                question.update({"questionId": str(uuid.uuid4())})

            if question["answerType"] == "TXT":
                del question["choices"]
            elif question["answerType"] == "MC":
                for choice in question["choices"]:
                    choice.update({"answerId": str(uuid.uuid4())})

        surveyMongo = mongo_client.update(
            collection="survey", content=content, query=query)
        surveyPostgresModel = {
            "form_id": id,
            "form_name": data.formName,
            "modify_dtm": datetime.datetime.utcnow(),
            "active": data.active,
            "modified_by": user_id
        }
        surveyPostgres = await update_form_postgres(surveyPostgresModel)

        if not surveyPostgres:
            return None

        if not surveyMongo:
            return None

        return surveyMongo
    except Exception:
        log.exception(
            f"Something went wrong when trying to update the survey with ID {id}")
        return None


async def update_quiz_func(id: str, data: update_quiz.Input, user_id: str):
    """Function to update a quiz

    Args:
        id (str): Id of the quiz to be updated
        data (update_survey.Input): All of the original form data (model) with whatever new needs to be added.

    Returns:
        bool: Returns true if updated, false if failed
    """

    try:
        if not data or not id:
            return None

        query = {"formId": id}
        content = {
            "formName": data.formName,
            "active": data.active,
            "attempts": data.attempts,
            "passingPoints": data.passingPoints,
            "duration": data.duration if data.duration else 0,
            "questions": [
                {
                    "questionId": question.questionId,
                    "questionNumber": question.questionNumber,
                    "description": question.description,
                    "answerType": question.answerType,
                    "active": question.active,
                    "pointValue": question.pointValue,
                    "choices": [
                        {
                            "description": choice.description,
                            "choicePosition": choice.choicePosition,
                            "active": choice.active,
                            "isCorrect": choice.isCorrect
                        }
                        for choice in question.choices
                    ] if question.choices else []
                }
                for question in data.questions
            ]
        }

        for question in content["questions"]:
            if not question['questionId']:
                question.update({"questionId": str(uuid.uuid4())})

            if not question["answerType"] == 'multipleChoice':
                continue

        quizMongo = mongo_client.update(
            collection="quiz", content=content, query=query)
        quizPostgresModel = {
            "form_id": id,
            "form_name": data.formName,
            "modify_dtm": datetime.datetime.utcnow(),
            "active": data.active,
            "modified_by": user_id
        }
        quizPostgres = await update_form_postgres(quizPostgresModel)

        if not quizPostgres:
            return None

        if not quizMongo:
            return None

        return quizMongo
    except Exception:
        log.exception(
            f"Something went wrong when trying to update the quiz with ID {id}")
        return None
