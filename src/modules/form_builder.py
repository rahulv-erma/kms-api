import uuid
import datetime


from src.api.api_models.forms import create_survey, create_quiz
from src.database.sql.form_functions import submit_form
from src.database.mongo import mongo_client


async def survey_builder(survey: create_survey.Input, user_id: str):
    """Function to build a survey

    Args:
        survey (create_survey.Input): Model of survey
        user_id (str): UserId that the survey belongs to

    Returns:
        dict: Returns the survey after being built
    """

    form_id = str(uuid.uuid4())
    cur_dtm = datetime.datetime.utcnow()
    form_doc = survey.dict()
    form_doc.update({"formId": form_id})
    for question in form_doc["questions"]:
        question.update({"questionId": str(uuid.uuid4())})

        if question["answerType"] == "TXT":
            del question["choices"]
        elif question["answerType"] == "MC":
            for choice in question["choices"]:
                choice.update({"answerId": str(uuid.uuid4())})

    submitted_survey = await submit_form(
        content={
            "form_id": form_id,
            "form_name": form_doc["formName"],
            "form_type": "survey",
            "create_dtm": cur_dtm,
            "modify_dtm": cur_dtm,
            "created_by": user_id,
            "modified_by": user_id,
            "active": form_doc["active"]
        }
    )

    if not submitted_survey:
        return None

    submitted_survey = mongo_client.insert(
        collection="survey", content=form_doc.copy())
    if not submitted_survey:
        return None

    return form_doc


async def quiz_builder(quiz: create_quiz.Input, user_id: str):
    """function to build a quiz

    Args:
        quiz (create_quiz.Input): model of the quiz needing to be built
        user_id (str): id of user that created the quiz

    Returns:
        dict: returns quiz back
    """

    form_id = str(uuid.uuid4())
    cur_dtm = datetime.datetime.utcnow()
    if not quiz.duration:
        quiz.duration = 0

    form_doc = quiz.dict()
    form_doc.update({"formId": form_id})
    for question in form_doc["questions"]:
        question.update({"questionId": str(uuid.uuid4())})
        if not question["answerType"] == 'multipleChoice':
            continue

    submitted_quiz = await submit_form(
        content={
            "form_id": form_id,
            "form_name": form_doc["formName"],
            "form_type": "quiz",
            "create_dtm": cur_dtm,
            "modify_dtm": cur_dtm,
            "created_by": user_id,
            "modified_by": user_id,
            "active": form_doc["active"]
        }
    )

    if not submitted_quiz:
        return None

    submitted_quiz = mongo_client.insert(
        collection="quiz", content=form_doc.copy())
    if not submitted_quiz:
        return None

    return form_doc
