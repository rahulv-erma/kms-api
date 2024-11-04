import datetime
from typing import List, Union, Tuple
import asyncpg

from src import log
from src.database.sql import get_connection, acquire_connection
from src.api.api_models.forms.list_forms import Form


async def submit_form(content: dict):
    """Function to create a form

    Args:
        content (dict): Entire dict/model of the form

    Returns:
        bool: True if created, false if failed
    """

    columns = []
    insert_values = []
    for key, value in content.items():
        columns.append(key)
        insert_values.append(value)

    query = """
        INSERT INTO forms
        ({})
        VALUES ({});
    """.format(', '.join(columns), ', '.join(['$' + str(i + 1) for i in range(len(insert_values))]))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, *insert_values)
        return True

    except asyncpg.exceptions.UniqueViolationError as err:
        key = err.args[0].split('duplicate key value violates unique constraint "')[
            1].split('"')[0]
        log.info(key)
        if key == "form_submissions_response_id_key":
            return "response_id already in use"

        return "Unknown error"

    except Exception:
        log.exception(
            f"An error occured while submitting form for form_id {content['form_id']}")

    return False


async def update_form_postgres(content: dict):
    """Function to update a form

    Args:
        content (dict): Entire dict/model of the form

    Returns:
        bool: True if updated, false if failed
    """

    form_id = content["form_id"]
    del content["form_id"]

    update_query = "UPDATE forms SET {} WHERE form_id = $1;".format(
        ', '.join([f"{key} = ${idx+2}" for idx,
                  key in enumerate(list(content.keys()))])
    )

    query_values = list(content.values())

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(update_query, form_id, *query_values)
        return True
    except Exception:
        log.exception(
            f"An error occured while updating form with ID {form_id}")

    return False


async def get_forms(form_type: Union[str, None] = None, page: int = None, pageSize: int = None) -> List[Form]:
    """Function to get forms via SQL

    Args:
        form_type (Union[str, None], optional): Type of form you want to get, survey or quiz. Defaults to None.

    Returns:
        List[Form]: Returns a list of forms
    """

    formatted_forms = []
    query = """
        SELECT
            form_id,
            form_name,
            form_type,
            active
        FROM forms
        ORDER BY create_dtm;
    """
    if page and pageSize:
        query = """
            SELECT
                form_id,
                form_name,
                form_type,
                active
            FROM forms
            ORDER BY create_dtm
            LIMIT $1 OFFSET $2;
        """

    if form_type:
        query = """
            SELECT
                form_id,
                form_name,
                form_type,
                active
            FROM forms where form_type = $1
            ORDER BY create_dtm;
        """
        if page and pageSize:
            query = """
                SELECT
                    form_id,
                    form_name,
                    form_type,
                    active
                FROM forms where form_type = $1
                ORDER BY create_dtm
                LIMIT $2 OFFSET $3;
            """

    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if form_type:
                if page and pageSize:
                    forms = await conn.fetch(query, form_type, pageSize, (page-1)*pageSize)
                else:
                    forms = await conn.fetch(query, form_type)
            else:
                if page and pageSize:
                    forms = await conn.fetch(query, pageSize, (page-1)*pageSize)
                else:
                    forms = await conn.fetch(query)

            if page and pageSize:
                total_pages = await conn.fetchrow("SELECT COUNT(*) FROM forms")
            if forms:
                for form in forms:
                    formatted_forms.append({
                        "formId": form[0],
                        "formName": form[1],
                        "formType": form[2],
                        "active": form[3]
                    })

    except Exception:
        log.exception("An error occured while getting forms")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return formatted_forms, int(total_pages)


async def get_form(form_type: str = None, form_id: str = None) -> Union[Form, None]:
    """function to get a form

    Args:
        form_type (str, optional): type of form needed to get, survey/quiz. Defaults to None.
        form_id (str, optional): id of the form to return. Defaults to None.

    Returns:
        Union[Form, None]: form in a model
    """

    if not form_type and not form_id:
        return None

    query = """
        SELECT
            form_id,
            form_name,
            form_type,
            active
        FROM forms where form_type = $1 AND form_id = $2;
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            form = await conn.fetchrow(query, form_type, form_id)
            if not form:
                return None

        return {
            "formId": form['form_id'],
            "formName": form['form_name'],
            "formType": form['form_type'],
            "active": form['active']
        }

    except Exception:
        log.exception("An error occured while getting forms")

    return None


async def is_form_related(course_id: str, form_id: str, user_id: str) -> Union[Tuple[bool, bool, int], None]:
    """Function to check if a course and form are related, and return users form attempts

    Args:
        course_id (str): course_id of the course
        form_id (str): form_id of the quiz
        user_id (str): user_id of the user

    Returns:
        Union[Tuple[bool, bool, int], None]: returns tuple with bools for each option, related, user is in course and int for total attempts
    """
    related_query = """
        SELECT
            *
        FROM course_forms
        where course_id = $1 AND form_id = $2;
    """

    user_in_course_query = """
        SELECT
            *
        FROM course_registration
        where course_id = $1 AND user_id = $2 AND registration_status = 'enrolled';
    """

    user_form_attempts = """
        SELECT
            fs.*
        FROM course_forms cf
        JOIN form_submissions fs
        ON cf.form_id = fs.form_id
        where cf.course_id = $1 AND cf.form_id = $2 and fs.user_id = $3;
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            related = await conn.fetchrow(related_query, course_id, form_id)
            if not related:
                return (False, False, None)

            user_check = await conn.fetchrow(user_in_course_query, course_id, user_id)
            if not user_check:
                return (True, False, None)

            user_attempts = await conn.fetchall(user_form_attempts, course_id, form_id, user_id)
            return (True, True, len(user_attempts) if user_attempts else None)

    except Exception:
        log.exception("An error occured while getting forms")

    return None


async def submit_quiz_submission(
    response_id: str,
    user_id: str,
    form_id: str,
    passing: bool,
    score: float,
    possible_score: float
):
    query = """
        INSERT INTO form_submissions (
            form_id,
            user_id,
            response_id,
            create_dtm,
            modify_dtm,
            passing,
            score,
            possible_score
        ) VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8
        )
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(
                query,
                form_id,
                user_id,
                response_id,
                datetime.datetime.utcnow(),
                datetime.datetime.utcnow(),
                passing,
                score,
                possible_score
            )
        return True

    except Exception:
        log.exception("An error occured while submitting form submission")
    return False


async def submit_survey_submission(
    response_id: str,
    user_id: str,
    form_id: str
):
    query = """
        INSERT INTO form_submissions (
            form_id,
            user_id,
            response_id,
            create_dtm,
            modify_dtm
        ) VALUES (
            $1,
            $2,
            $3,
            $4,
            $5
        )
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, form_id, user_id, response_id, datetime.datetime.utcnow(), datetime.datetime.utcnow())
        return True

    except Exception:
        log.exception("An error occured while submitting form submission")
    return False


async def get_course_forms(course_id: str, page: int = None, pageSize: int = None) -> List[Form]:
    """Function to get forms via SQL

    Args:
        form_type (Union[str, None], optional): Type of form you want to get, survey or quiz. Defaults to None.

    Returns:
        List[Form]: Returns a list of forms
    """

    formatted_forms = []
    query = """
        SELECT
            f.form_id,
            f.form_name,
            f.form_type,
            f.active
        FROM course_forms cf
        JOIN forms f on cf.form_id = f.form_id
        where cf.course_id = $1
        ORDER BY create_dtm;
    """

    if page and pageSize:
        query.replace(';', ' LIMIT $2 OFFSET $3;')
    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                forms = await conn.fetch(query, course_id, pageSize, (page-1)*pageSize)
                total_pages = await conn.fetchrow("SELECT COUNT(*) FROM course_forms")
            else:
                forms = await conn.fetch(query, course_id)
            if forms:
                for form in forms:
                    formatted_forms.append({
                        "formId": form[0],
                        "formName": form[1],
                        "formType": form[2],
                        "active": form[3]
                    })

    except Exception:
        log.exception("An error occured while getting forms")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return formatted_forms, int(total_pages)
