from fastapi import APIRouter, Depends
import json

from src import log
from src.api.lib.auth.auth import AuthClient
from src.modules.form_builder import survey_builder, quiz_builder
from src.api.lib.base_responses import successful_response, server_error, user_error
from src.api.api_models import global_models, pagination
from src.api.api_models.forms import (
    create_survey,
    create_quiz,
    list_forms,
    update_survey,
    update_quiz,
    quiz_load,
    survey_load,
    submit_quiz,
    submit_survey
)
from src.database.sql.audit_log_functions import submit_audit_record
from src.database.sql.form_functions import (
    get_forms,
    get_form,
    is_form_related,
    submit_quiz_submission,
    submit_survey_submission,
    get_course_forms
)
from src.database.sql.user_functions import get_user_roles
from src.database.mongo.mongo_functions import save_quiz_submission, save_survey_submission, get_form_from_mongo, update_survey_func, update_quiz_func


router = APIRouter(
    prefix="/forms",
    tags=["Forms"],
    responses={404: {"description": "Details not found"}}
)


@router.post(
    "/survey/create",
    description="Route to create a survey",
    response_model=create_survey.Output
)
async def create_survey_route(content: create_survey.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        survey = await survey_builder(survey=content, user_id=user.userId)
        if not survey:
            log.exception("Failed to create survey")
            return server_error(
                message="Failed to create survey"
            )

        await submit_audit_record(
            route="forms/survey/create",
            details=f"User {user.firstName} {user.lastName} created survey {survey['formId']}",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to create survey")
        return server_error(
            message="Failed to create survey"
        )


@router.post(
    "/survey/update",
    description="Route to update a survey",
    response_model=update_survey.Output
)
async def update_survey_route(content: update_survey.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        if not content.formId:
            return user_error(message="Survey ID must be provided.")

        if not content:
            return user_error(message="You must specify what you would like to update about this survey")

        form = await get_form(form_type="survey", form_id=content.formId)

        if not form:
            return user_error(message="Form does not exist with this ID.")

        updatedSurvey = await update_survey_func(content.formId, content, user_id=user.userId)

        if not updatedSurvey:
            return user_error(message="Survey could not be updated")

        await submit_audit_record(
            route="forms/survey/update",
            details=f"User {user.firstName} {user.lastName} updated survey {content.formId} with values {json.dumps(content.dict())}",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to update survey")
        return server_error(message="Failed to update survey")


@router.get(
    "/survey/load/{formId}",
    description="Route to load a survey",
    response_model=survey_load.Output
)
async def load_survey(formId: str):
    try:
        form = await get_form_from_mongo("survey", formId)
        if not form:
            return user_error(message="Failed to find a survey with this ID")

        return successful_response(payload={"form": form})
    except Exception:
        log.exception("Failed to load survey")
        return server_error(message="Failed to load survey")


@router.post(
    "/quiz/create",
    description="Route to create a quiz",
    response_model=create_quiz.Output
)
async def create_quiz_route(content: create_quiz.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        quiz = await quiz_builder(quiz=content, user_id=user.userId)
        if not quiz:
            log.exception("Failed to create quiz")
            return server_error(
                message="Failed to create quiz"
            )

        await submit_audit_record(
            route="forms/quiz/create",
            details=f"User {user.firstName} {user.lastName} created quiz {quiz['formId']}",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to create quiz")
        return server_error(
            message="Failed to create quiz"
        )


@router.post(
    "/quiz/update",
    description="Route to update a quiz",
    response_model=update_quiz.Output
)
async def update_quiz_route(content: update_quiz.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        if not content.formId:
            return user_error(message="Quiz ID must be provided.")

        if not content:
            return user_error(message="You must specify content to update.")

        form = await get_form(form_type="quiz", form_id=content.formId)

        if not form:
            return user_error(message="Form does not exist with this ID.")

        updatedQuiz = await update_quiz_func(content.formId, content, user_id=user.userId)

        if not updatedQuiz:
            return user_error(message="Quiz could not be updated")

        await submit_audit_record(
            route="forms/quiz/update",
            details=f"User {user.firstName} {user.lastName} updated quiz {content.formId} with values {json.dumps(content.dict())}",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to update Quiz")
        return server_error(message="Failed to update Quiz")


@router.get(
    "/quiz/load/{formId}",
    description="Route to load a quiz",
    response_model=quiz_load.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def load_quiz(formId: str, showCorrect: bool = False, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        user_roles = await get_user_roles(user.userId)
        if not user_roles:
            return server_error("An error occured while loading quiz")

        # if showCorrect and not any(role["roleName"] Win ["instructor", "admin", "superuser"] for role["roleName"] in user_roles):
        #     showCorrect = False

        form = await get_form_from_mongo("quiz", formId)
        if not form:
            return user_error(message="Failed to find a quiz with this ID")

        if not showCorrect:
            for question in form["questions"]:
                newChoices = []
                for choice in question["choices"]:
                    del choice["isCorrect"]
                    newChoices.append(choice)
                question["choices"] = newChoices

        return successful_response(payload={"form": form})
    except Exception:
        log.exception("Failed to load survey")
        return server_error(message="Failed to load survey")


@router.get(
    "/list",
    description="Route to list all forms",
    response_model=list_forms.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def list_forms_route(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        forms, total_pages = await get_forms(form_type=None, page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "forms": forms,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception("Failed to get forms")
        return server_error(
            message="Failed to get forms"
        )


@router.get(
    "/list/quiz",
    description="Route to list all forms",
    response_model=list_forms.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def list_quiz_route(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        forms, total_pages = await get_forms(form_type="quiz", page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "forms": forms,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception("Failed to get quizzes")
        return server_error(
            message="Failed to get quizzes"
        )


@router.get(
    "/list/survey",
    description="Route to list all forms",
    response_model=list_forms.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def list_survey_route(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        forms, total_pages = await get_forms(form_type="survey", page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "forms": forms,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception("Failed to get surveys")
        return server_error(
            message="Failed to get surveys"
        )


# TODO: this needs to be tested
@router.get(
    "/quiz/submit/{courseId}/{quizId}",
    description="Route to submit quiz attempt",
    response_model=submit_quiz.Output
)
async def submit_quiz_route(courseId: str, quizId: str, content: submit_quiz.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        # check to see if quiz is related to course and get all users quiz attempts
        related, enrolled, user_attempts = await is_form_related(course_id=courseId, quiz_id=quizId, user_id=user.userId)
        # if not/nothing return error
        if not related:
            return user_error(
                message="Course does not have quiz"
            )

        if not enrolled:
            return user_error(
                message="User is not enrolled in course"
            )
        # get quiz
        quiz = await get_form_from_mongo("quiz", quizId)
        if not quiz:
            return server_error(
                message="failed to get quiz"
            )

        # check user attempts of quiz
        # if passed total amount return error
        if quiz["attempts"] <= user_attempts:
            return user_error(
                message="User has already exceeded max attempts"
            )

        # grade quiz
        earned_points = 0
        passing_score = quiz["passingPoints"]
        possible_score = 0
        content = content.dict()
        for submitted_question in content:
            submitted_question["questionId"]
            for question in quiz["questions"]:
                if not question["questionId"] == submitted_question["questionId"] or not question["answerType"] == 'MC':
                    continue
                submitted_question["pointValue"] = question["pointValue"]
                possible_score += question["pointValue"]
                if not submitted_question.get("answer"):
                    continue

                for choice in question["choices"]:
                    if (
                        not choice["choicePosition"] == submitted_question["answer"]["choicePosition"] or
                        not choice["description"] == submitted_question["answer"]["description"]
                    ):
                        continue
                    if choice["isCorrect"]:
                        earned_points += question["pointValue"]
                        submitted_question.update({"correct": True})
            quiz["questions"].remove(question)

        passing = True if earned_points >= passing_score else False
        # save attempt
        response_id = await save_quiz_submission(
            content=content,
            form_id=quizId,
            user_id=user.userId,
            passing=passing,
            score=earned_points,
            possible_points=possible_score,
            attempts=user_attempts
        )
        if not response_id:
            return server_error(
                message="Failed to submit survey"
            )

        if not await submit_quiz_submission(
            response_id=response_id,
            user_id=user.userId,
            form_id=quizId,
            passing=passing,
            score=earned_points,
            possible_score=possible_score
        ):
            return server_error(
                message="Failed to submit quiz"
            )
        # return
        return successful_response(
            payload={
                "passing": passing,
                "retake": True if user_attempts + 1 < quiz["attempts"] else None,
                "score": f"{((earned_points/passing_score)*100)}%",
                "neededScore": f"{passing_score}%"
            }
        )

    except Exception:
        log.exception("Failed to submit quiz")
        return server_error(
            message="Failed to submit quiz"
        )


# TODO: this needs to be tested
@router.get(
    "/survey/submit/{courseId}/{quizId}",
    description="Route to submit survey attempt",
    response_model=submit_survey.Output
)
async def submit_survey_route(
    courseId: str,
    surveyId: str,
    content: submit_survey.Input,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        # check to see if quiz is related to course and get all users quiz attempts
        related, enrolled, _ = await is_form_related(course_id=courseId, survey_id=surveyId, user_id=user.userId)
        # if not/nothing return error
        if not related:
            return user_error(
                message="Course does not have a survey with this ID"
            )

        if not enrolled:
            return user_error(
                message="User is not enrolled in this course"
            )

        response_id = await save_survey_submission(
            content=content,
            form_id=surveyId,
            user_id=user.userId
        )
        if not response_id:
            return server_error(message="Failed to submit survey")

        if not await submit_survey_submission(
            response_id=response_id,
            user_id=user.userId,
            form_id=surveyId
        ):
            return server_error(
                message="Failed to submit quiz"
            )
        return successful_response()

    except Exception:
        log.exception("Failed to submit survey")
        return server_error(
            message="Failed to submit survey"
        )


@router.get(
    "/list/{courseId}",
    description="Route to list all of a courses forms",
    response_model=list_forms.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def list_course_forms_route(courseId: str, page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        forms, total_pages = await get_course_forms(course_id=courseId, page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "forms": forms,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception("Failed to get forms")
        return server_error(
            message="Failed to get forms"
        )
