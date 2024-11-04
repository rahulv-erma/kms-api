from typing import Union
import datetime
import os

from src import log
from src.utils.snake_case import camel_to_snake
from src.api.api_models import global_models
from src.api.api_models.courses import course_update, create, bundle_update, bundle
from src.database.sql import get_connection, acquire_connection


async def list_courses(
    ignore_bundle: bool = False,
    enrollment: bool = False,
    page: int = None,
    pageSize: int = None
) -> list:
    """Function to get a list of courses

    Args:
        ignore_bundle (bool, optional): Ingore bundled courses bool. Defaults to False.
        active (bool, optional): If course is active. Defaults to False.
        enrollment (bool, optional): If course is enrollable. Defaults to False.
        waitlist (bool, optional): If course has a waitlist. Defaults to False.

    Returns:
        list: List of courses
    """

    where_condition = None
    coursesList = []
    conditions = []

    if enrollment:
        conditions.append("c.active = true")
        conditions.append("c.is_complete = false")
        conditions.append("(c.waitlist = true or c.is_full = false)")

    if ignore_bundle:
        conditions.append("bc.course_id IS NULL")

    query = """
        SELECT
            c.course_picture,
            c.course_id,
            c.course_name,
            c.first_class_dtm,
            c.brief_description,
            c.classes_in_series,
            c.active,
            c.is_complete,
            c.create_dtm
        FROM courses AS c
        ORDER BY c.create_dtm DESC;
    """

    if page and pageSize:
        query = """
            SELECT
                c.course_picture,
                c.course_id,
                c.course_name,
                c.first_class_dtm,
                c.brief_description,
                c.classes_in_series,
                c.active,
                c.is_complete,
                c.create_dtm
            FROM courses AS c
            ORDER BY c.create_dtm DESC
            LIMIT $1 OFFSET $2;
        """

    if conditions:
        where_condition = " AND ".join(conditions)
        query = """
            SELECT
                c.course_picture,
                c.course_id,
                c.course_name,
                c.first_class_dtm,
                c.brief_description,
                c.classes_in_series,
                c.active,
                c.is_complete,
                c.create_dtm
            FROM courses AS c
            LEFT JOIN bundled_courses AS bc
            ON c.course_id = bc.course_id
            WHERE {}
            ORDER BY c.create_dtm DESC;
        """.format(where_condition)

        if page and pageSize:
            query = """
                SELECT
                    c.course_picture,
                    c.course_id,
                    c.course_name,
                    c.first_class_dtm,
                    c.brief_description,
                    c.classes_in_series,
                    c.active,
                    c.is_complete,
                    c.create_dtm
                FROM courses AS c
                LEFT JOIN bundled_courses AS bc
                ON c.course_id = bc.course_id
                WHERE {}
                ORDER BY c.create_dtm DESC
                LIMIT $1 OFFSET $2;
            """.format(where_condition)

    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                if conditions:
                    total_pages = await conn.fetchrow("""
                        SELECT
                            COUNT(*)
                        FROM courses AS c
                        LEFT JOIN bundled_courses AS bc
                        ON c.course_id = bc.course_id
                        WHERE {};
                    """.format(where_condition))
                else:
                    total_pages = await conn.fetchrow("""
                        SELECT
                            COUNT(*)
                        FROM courses AS c
                        LEFT JOIN bundled_courses AS bc
                        ON c.course_id = bc.course_id;
                    """)
                courses = await conn.fetch(query, pageSize, (page-1)*pageSize)
            else:
                courses = await conn.fetch(query)

            if courses:
                for course in courses:
                    course_object = {
                        "coursePicture": course['course_picture'],
                        "courseId": course['course_id'],
                        "courseName": course['course_name'],
                        "startDate": (datetime.datetime.strftime(course['first_class_dtm'], "%m/%d/%Y %-I:%M %p")
                                      if course['first_class_dtm'] else None),
                        "briefDescription": course['brief_description'],
                        "totalClasses": course['classes_in_series'],
                        "courseType": "Course",
                        "active": course['active'],
                        "complete": course['is_complete']
                    }
                    coursesList.append(course_object)

    except Exception:
        log.exception("An error occured while getting courses list")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return coursesList, int(total_pages)


async def get_course(course_id: str = None, full_details: bool = False) -> Union[None, tuple]:
    """Function to get a course

    Args:
        course_id (str, optional): Course Id to get the course wanted. Defaults to None.

    Returns:
        Union[None, global_models.Course]: Model of a course with values
    """
    if not course_id:
        return None

    course = None

    query = """
        SELECT
            c.course_id,
            c.course_name,
            c.brief_description,
            c.course_picture,
            c.price,
            c.languages,
            c.instruction_types,
            c.active,
            c.max_students,
            c.is_full,
            c.waitlist,
            c.first_class_dtm,
            c.enrollment_start_date,
            c.registration_expiration_dtm,
            c.description,
            c.email,
            c.phone_number,
            c."address",
            c.remote_link,
            c.waitlist_limit,
            c.allow_cash,
            c.course_code
        FROM
            courses c
        WHERE
            c.course_id = $1
        GROUP BY
            c.course_id;
    """

    prerequisitesQuery = """
        SELECT
            c.course_id,
            c.course_name
            FROM courses c
            LEFT JOIN prerequisites p
            on c.course_id = p.prerequisite
            where p.course_id = $1;
    """

    instructorsQuery = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name
            FROM users u
            JOIN course_instructor ci
            ON u.user_id = ci.user_id
            WHERE ci.course_id = $1;
    """

    scheduleQuery = """
        SELECT
            is_complete,
            course_id,
            series_number,
            start_dtm,
            end_dtm
        FROM course_dates
        WHERE course_id = $1;
    """

    formQuery = """
        SELECT
            cf.form_id,
            cf.form_name,
            cf.course_id,
            f.form_type
        FROM course_forms cf
        LEFT JOIN forms f ON cf.form_id = f.form_id
        GROUP BY cf.form_id, cf.form_name, cf.course_id, f.form_type
        WHERE cf.course_id = $1;
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found_course = await conn.fetchrow(query, course_id)
            prerequisites = await conn.fetch(prerequisitesQuery, course_id)
            found_schedule = await conn.fetch(scheduleQuery, course_id)
            instructors = await conn.fetch(instructorsQuery, course_id)

            if full_details:
                forms = await conn.fetch(formQuery, course_id)
                quiz = []
                survey = []
                if forms:
                    for f in forms:
                        if f['form_type'] == "quiz":
                            quiz.append(f)
                        elif f['form_type'] == "survey":
                            survey.append(f)

            if found_course:
                course = {
                    "courseId": found_course['course_id'],
                    "courseName": found_course['course_name'],
                    "briefDescription": found_course['brief_description'],
                    "coursePicture": found_course['course_picture'],
                    "price": found_course['price'],
                    "prerequisites": [],
                    "languages": found_course['languages'],
                    "instructionTypes": found_course['instruction_types'],
                    "active": found_course['active'],
                    "maxStudents": found_course['max_students'],
                    "isFull": found_course['is_full'],
                    "waitlist": found_course['waitlist'],
                    "startDate": found_course['first_class_dtm'].strftime("%m/%d/%Y %-I:%M %p"),
                    "description": found_course['description'],
                    "instructors": [],
                    "email": found_course['email'],
                    "phoneNumber": found_course['phone_number'],
                    "address": found_course['address'],
                    "remoteLink": found_course['remote_link'],
                    "waitlistLimit": found_course['waitlist_limit'],
                    "allowCash": found_course['allow_cash'],
                    "courseCode": found_course['course_code']
                }

                if found_course['enrollment_start_date']:
                    enrollable = True if found_course['enrollment_start_date'] <= datetime.datetime.utcnow(
                    ) <= found_course['registration_expiration_dtm'] else False
                else:
                    enrollable = False
                course.update({"enrollable": enrollable})

                if full_details:
                    course.update({"quiz": quiz})
                    course.update({"survey": survey})

                if instructors:
                    for instructor in instructors:
                        course["instructors"].append({
                            "userId": instructor['user_id'],
                            "firstName": instructor['first_name'],
                            "lastName": instructor['last_name']
                        })

                if prerequisites:
                    for prereq in prerequisites:
                        course["prerequisites"].append({
                            "courseId": prereq['course_id'],
                            "courseName": prereq['course_name']
                        })

                schedule = []
                if found_schedule:
                    for event in found_schedule:
                        schedule.append({
                            "courseId": event['course_id'],
                            "courseName": found_course['course_name'],
                            "startTime": event['start_dtm'].strftime("%m/%d/%Y %-I:%M %p"),
                            "endTime": event['end_dtm'].strftime("%m/%d/%Y %-I:%M %p"),
                            "duration": (event['end_dtm'] - event['start_dtm']).total_seconds() // 60,
                            "seriesNumber": event['series_number'],
                            "complete": event['is_complete']
                        })

        return (
            course,
            schedule
        )
    except Exception:
        log.exception(
            f"An error occured while getting course with course_id {course_id}")

    return (None, None)


async def update_enrollment(course_id: str, user_id: str, status: str, paid: bool = None, notes: str = None):

    queries = []
    if status:
        query = """
            UPDATE
                course_registration
            SET
                registration_status=$1
            WHERE
                user_id=$2 AND course_id=$3;
        """
        queries.append((query, [status, user_id, course_id]))

    if paid:
        query = """
            UPDATE
                course_registration
            SET
                user_paid=$1
            WHERE
                user_id=$2 AND course_id=$3;
        """
        queries.append((query, [paid, user_id, course_id]))

    if notes:
        query = """
            UPDATE
                course_registration
            SET
                user_paid=$1
            WHERE
                user_id=$2 AND course_id=$3;
        """
        queries.append((query, [notes, user_id, course_id]))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            for insert in queries:
                await conn.execute(insert[0], *insert[1])
        return True
    except Exception:
        log.exception(
            f"An error occured while updating the enrollment for the user {user_id} in {course_id}")
        return False


async def check_course_registration(course_id: str = None, user_id: str = None):
    course = await get_course(course_id=course_id)

    if not course[0]:
        return None

    course = course[0]

    query = """
        SELECT
            cr.course_id,
            cr.user_id,
            cr.registration_status,
            cr.student_registration_date,
            cr.enroll_date,
            cr.denial_reason,
            cr.user_paid,
            cr.user_paying_cash,
            c.auto_student_enrollment
        FROM
            course_registration  cr
        JOIN courses c on c.course_id = cr.course_id
        WHERE cr.course_id = $1 AND cr.registration_status IN ('enrolled', 'waitlist', 'pending');
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            users = await conn.fetch(query, course_id)

        enrolled = []
        waitlist = []
        course_data = {
            "courseId": course_id,
            "isFull": course["isFull"],
            "waitlist": course["waitlist"],
            "enrollable": course["enrollable"],
            "complete": course["complete"]
        }
        change = False
        if users:
            for u in users:
                if user_id == u['user_id']:
                    return "User already enrolled"
                if u['registration_status'] == "enrolled":
                    enrolled.append(u)
                elif u['registration_status'] == "waitlist":
                    waitlist.append(u)
                # course_data["pending"] = u[4]

        if not course["isFull"] and len(enrolled) >= course["maxStudents"]:
            course_data["isFull"] = True
            change = True
        if course["waitlist"] and len(waitlist) >= course["waitlistLimit"]:
            course_data["waitlist"] = False
            change = True

        if change:
            updated = course_update.UpdateCourseInput(
                courseId=course_data["courseId"],
                isFull=course_data["isFull"],
                waitlist=course_data["waitlist"]
            )
            await update_course(updated)

        return course_data

    except Exception:
        log.exception(
            f"An error occured while getting students registration type for {course_id}")

    return None


async def check_bundle_registration(bundle_id: str = None, user_id: str = None):
    bundle = await get_bundle(bundle_id=bundle_id)

    if not bundle[0]:
        return None

    bundle = bundle[0]

    course_ids = [course["courseId"] for course in bundle["courses"]]

    query = """
        SELECT
            cr.course_id,
            cr.user_id,
            cr.registration_status,
            cr.student_registration_date,
            cr.enroll_date,
            cr.denial_reason,
            cr.user_paid,
            cr.user_paying_cash,
            c.auto_student_enrollment
        FROM
            course_registration  cr
        JOIN courses c on c.course_id = cr.course_id
        WHERE cr.course_id IN ({}) AND cr.registration_status IN ('enrolled', 'waitlist', 'pending');
    """.format(', '.join(['$' + str(i + 1) for i in range(len(course_ids))]))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            users = await conn.fetch(query, *course_ids)
        enrolled = []
        waitlist = []
        bundle_data = {
            "bundleId": bundle_id,
            "isFull": bundle["isFull"],
            "enrollable": bundle["enrollable"],
            "waitlist": bundle["waitlist"],
            "courses": bundle["courses"],
            "complete": bundle["complete"]
        }

        change = False
        if users:
            for u in users:
                if user_id == u['user_id']:
                    return "User already enrolled"
                if u['registration_status'] == "enrolled":
                    enrolled.append(u)
                elif u['registration_status'] == "waitlist":
                    waitlist.append(u)
                # course_data["pending"] = u[4]

        if not bundle["isFull"] and len(enrolled)/3 >= bundle["maxStudents"]:
            bundle_data["isFull"] = True
            change = True
        if bundle["waitlist"] and len(waitlist)/3 >= bundle["waitlistLimit"]:
            bundle_data["waitlist"] = False
            change = True

        if change:
            updated = bundle_update.UpdateBundleInput(
                bundleId=bundle_data["bundleId"],
                isFull=bundle_data["isFull"],
                waitlist=bundle_data["waitlist"]
            )
            await update_bundle(updated)

        return bundle_data

    except Exception:
        log.exception(
            f"An error occured while getting students registration type for {bundle_id}")

    return None


async def get_schedule(user_id: str = None, page: int = None, pageSize: int = None) -> list:
    """Get a schedule for a user

    Args:
        user_id (str, optional): User Id to get the schedule of. Defaults to None.

    Returns:
        list: A list of schedules
    """

    if not user_id:
        return []
    current_timestamp = datetime.datetime.now()

    query = """
        SELECT
            c.course_id,
            c.course_name,
            cd.start_dtm,
            cd.end_dtm,
            cd.series_number,
            cd.is_complete
        FROM
            courses c
        JOIN
            course_dates cd ON c.course_id = cd.course_id
        WHERE
            EXISTS (
                SELECT 1
                FROM course_instructor ci
                WHERE ci.course_id = c.course_id AND ci.user_id = $1
            )
            OR EXISTS (
                SELECT 1
                FROM course_registration cr
                WHERE cr.course_id = c.course_id AND cr.user_id = $1
            )
            AND cd.start_dtm > $2
        ORDER BY
            cd.start_dtm ASC;
    """

    if page and pageSize:
        query = """
            SELECT
                c.course_id,
                c.course_name,
                cd.start_dtm,
                cd.end_dtm,
                cd.series_number,
                cd.is_complete
            FROM
                courses c
            JOIN
                course_dates cd ON c.course_id = cd.course_id
            WHERE
                EXISTS (
                    SELECT 1
                    FROM course_instructor ci
                    WHERE ci.course_id = c.course_id AND ci.user_id = $1
                )
                OR EXISTS (
                    SELECT 1
                    FROM course_registration cr
                    WHERE cr.course_id = c.course_id AND cr.user_id = $1
                )
                AND cd.start_dtm > $2
            ORDER BY
                cd.start_dtm ASC
            LIMIT $3 OFFSET $4;
        """
    formatted_schedule = []
    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                schedule = await conn.fetch(query, user_id, current_timestamp, page, pageSize)
                total_pages = await conn.fetchrow("""
                    SELECT
                        COUNT(*)
                    FROM
                        courses c
                    JOIN
                        course_dates cd ON c.course_id = cd.course_id
                    WHERE
                        EXISTS (
                            SELECT 1
                            FROM course_instructor ci
                            WHERE ci.course_id = c.course_id AND ci.user_id = $1
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM course_registration cr
                            WHERE cr.course_id = c.course_id AND cr.user_id = $1
                        )
                        AND cd.start_dtm > $2;
                """, user_id, current_timestamp)
            else:
                schedule = await conn.fetch(query, user_id, current_timestamp)
            if schedule:
                for course in schedule:
                    formatted_schedule.append({
                        "courseId": course[0],
                        "courseName": course[1],
                        "startTime": str(course[2]),
                        "endTime": str(course[3]),
                        "duration": (course[3] - course[2]).total_seconds() // 60,
                        "seriesNumber": course[4],
                        "complete": course[5]
                    })

    except Exception:
        log.exception(
            f"An error occured while getting courses related to {user_id}")

    if total_pages:
        total_pages = total_pages[0]/pageSize
    return formatted_schedule, int(total_pages)


async def search_courses(course_name: str = None, course_bundle: str = None, catalog: bool = False, page: int = None, pageSize: int = None) -> tuple:
    """Function to search for a course

    Args:
        course_name (str, optional): Course name needed to find the course. Defaults to None.
        course_bundle (str, optional): Bundle name needed to find the course bundle. Defaults to None.
        catalog (bool, optional): depicts whether not its for the catalog for students. Defaults to None.

    Returns:
        Tuple[list, list]: A list of courses
    """

    query = None
    value = None

    if course_name:
        value = f'%{course_name}%'
        query = """
            SELECT
                c.course_picture,
                c.course_id,
                c.course_name,
                c.first_class_dtm,
                c.brief_description,
                c.classes_in_series,
                c.active,
                c.is_complete,
                c.create_dtm
            FROM courses AS c
            where c.course_name LIKE $1
            ORDER BY c.create_dtm DESC;
        """
        if page and pageSize:
            query = """
                SELECT
                    c.course_picture,
                    c.course_id,
                    c.course_name,
                    c.first_class_dtm,
                    c.brief_description,
                    c.classes_in_series,
                    c.active,
                    c.is_complete,
                    c.create_dtm
                FROM courses AS c
                where c.course_name LIKE $1
                ORDER BY c.create_dtm DESC
                LIMIT $2 OFFSET $3;
            """
        if catalog:
            query = """
                SELECT
                    c.course_picture,
                    c.course_id,
                    c.course_name,
                    c.first_class_dtm,
                    c.brief_description,
                    c.classes_in_series,
                    c.active,
                    c.is_complete,
                    c.create_dtm
                FROM courses AS c
                where c.course_name LIKE $1
                and c.is_complete = false
                and c.active = true
                and c.is_full = false
                and c.waitlist = true
                and c.registration_expiration_dtm > CURRENT_TIMESTAMP
                ORDER BY c.create_dtm DESC;
            """
            if page and pageSize:
                query = """
                    SELECT
                        c.course_picture,
                        c.course_id,
                        c.course_name,
                        c.first_class_dtm,
                        c.brief_description,
                        c.classes_in_series,
                        c.active,
                        c.is_complete,
                        c.create_dtm
                    FROM courses AS c
                    where c.course_name LIKE $1
                    and c.is_complete = false
                    and c.active = true
                    and c.is_full = false
                    and c.waitlist = true
                    and c.registration_expiration_dtm > CURRENT_TIMESTAMP
                    ORDER BY c.create_dtm DESC
                    LIMIT $2 OFFSET $3;
                """
    if course_bundle:
        value = f'%{course_bundle}%'
        query = """
            SELECT
            cb.bundle_photo,
            cb.bundle_id,
            cb.bundle_name,
            cb.active,
            cb.is_complete,
            SUM(c.classes_in_series) AS total_classes,
            cb.create_dtm
            FROM
                course_bundles cb
            JOIN
                bundled_courses bc ON cb.bundle_id = bc.bundle_id
            JOIN
                courses c ON bc.course_id = c.course_id
            where cb.bundle_name LIKE $1
            and cb.is_complete = false
            and cb.active = true
            and cb.is_full = false
            and cb.waitlist = true
            and cb.registration_expiration_dtm > CURRENT_TIMESTAMP
            GROUP BY
                cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
            ORDER BY
                cb.create_dtm DESC;
        """
        if page and pageSize:
            query = """
                SELECT
                cb.bundle_photo,
                cb.bundle_id,
                cb.bundle_name,
                cb.active,
                cb.is_complete,
                SUM(c.classes_in_series) AS total_classes,
                cb.create_dtm
                FROM
                    course_bundles cb
                JOIN
                    bundled_courses bc ON cb.bundle_id = bc.bundle_id
                JOIN
                    courses c ON bc.course_id = c.course_id
                where cb.bundle_name LIKE $1
                and cb.is_complete = false
                and cb.active = true
                and cb.is_full = false
                and cb.waitlist = true
                and cb.registration_expiration_dtm > CURRENT_TIMESTAMP
                GROUP BY
                    cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                ORDER BY
                    cb.create_dtm DESC
                LIMIT $2 OFFSET $3;
            """
        if catalog:
            query = """
                SELECT
                cb.bundle_photo,
                cb.bundle_id,
                cb.bundle_name,
                cb.active,
                cb.is_complete,
                SUM(c.classes_in_series) AS total_classes,
                cb.create_dtm
                FROM
                    course_bundles cb
                JOIN
                    bundled_courses bc ON cb.bundle_id = bc.bundle_id
                JOIN
                    courses c ON bc.course_id = c.course_id
                where cb.bundle_name LIKE $1
                GROUP BY
                    cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                ORDER BY
                    cb.create_dtm DESC;
            """
            if page and pageSize:
                query = """
                    SELECT
                    cb.bundle_photo,
                    cb.bundle_id,
                    cb.bundle_name,
                    cb.active,
                    cb.is_complete,
                    SUM(c.classes_in_series) AS total_classes,
                    cb.create_dtm
                    FROM
                        course_bundles cb
                    JOIN
                        bundled_courses bc ON cb.bundle_id = bc.bundle_id
                    JOIN
                        courses c ON bc.course_id = c.course_id
                    where cb.bundle_name LIKE $1
                    GROUP BY
                        cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                    ORDER BY
                        cb.create_dtm DESC
                    LIMIT $2 OFFSET $3;
                """
    courses = []
    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                found_courses = await conn.fetch(query, value, pageSize, (page-1)*pageSize)
                if course_name and not catalog:
                    total_pages = await conn.fetchrow("""
                        SELECT
                            COUNT(*)
                        FROM courses AS c
                        where c.course_name LIKE $1;
                    """, course_name)
                if course_name and catalog:
                    total_pages = await conn.fetchrow("""
                        SELECT
                            c.course_picture,
                            c.course_id,
                            c.course_name,
                            c.first_class_dtm,
                            c.brief_description,
                            c.classes_in_series,
                            c.active,
                            c.is_complete,
                            c.create_dtm
                        FROM courses AS c
                        where c.course_name LIKE $1
                        and c.is_complete = false
                        and c.active = true
                        and c.is_full = false
                        and c.waitlist = true
                        and c.registration_expiration_dtm > CURRENT_TIMESTAMP;
                    """, course_name)
                if course_bundle and not catalog:
                    total_pages = await conn.fetchrow("""
                        SELECT
                        COUNT(*)
                        FROM
                            course_bundles cb
                        JOIN
                            bundled_courses bc ON cb.bundle_id = bc.bundle_id
                        JOIN
                            courses c ON bc.course_id = c.course_id
                        where cb.bundle_name LIKE $1
                        and cb.is_complete = false
                        and cb.active = true
                        and cb.is_full = false
                        and cb.waitlist = true
                        and cb.registration_expiration_dtm > CURRENT_TIMESTAMP
                        GROUP BY
                            cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                        ORDER BY
                            cb.create_dtm DESC;
                    """, course_bundle)
                if course_bundle and catalog:
                    total_pages = await conn.fetchrow("""
                        SELECT
                        cb.bundle_photo,
                        cb.bundle_id,
                        cb.bundle_name,
                        cb.active,
                        cb.is_complete,
                        SUM(c.classes_in_series) AS total_classes,
                        cb.create_dtm
                        FROM
                            course_bundles cb
                        JOIN
                            bundled_courses bc ON cb.bundle_id = bc.bundle_id
                        JOIN
                            courses c ON bc.course_id = c.course_id
                        where cb.bundle_name LIKE $1
                        GROUP BY
                            cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                        ORDER BY
                            cb.create_dtm DESC;
                    """, course_bundle)
            else:
                found_courses = await conn.fetch(query, value)
            if found_courses:
                if course_name:
                    for course in found_courses:
                        courses.append({
                            "coursePicture": course['course_picture'],
                            "courseId": course['course_id'],
                            "courseName": course['course_name'],
                            "startDate": datetime.datetime.strftime(course['first_class_dtm'], "%m/%d/%Y %-I:%M %p"),
                            "briefDescription": course['brief_description'],
                            "totalClasses": course['classes_in_series'],
                            "courseType": "Course",
                            "active": course['active'],
                            "complete": course['is_complete']
                        })

                if course_bundle:
                    for course in found_courses:
                        courses.append({
                            "bundlePicture": course['bundle_photo'],
                            "bundleId": course['bundle_id'],
                            "bundleName": course['bundle_name'],
                            "active": course['active'],
                            "complete": course['is_complete'],
                            "totalClasses": course['total_classes'],
                            "courseType": "Bundle"
                        })

    except Exception:
        log.exception(
            f"An error occured while getting courses related to {value}")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return courses, int(total_pages)


async def assign_course(course_id: str = None, students: list = None, instructors: list = None):
    """Function to assign a course to students or instructors

    Args:
        course_id (str, optional): Course Id to assign to user. Defaults to None.
        students (list, optional): List of students to be assigned to course. Defaults to None.
        instructors (list, optional): List of students to be assigned to course. Defaults to None.

    Raises:
        ValueError: If students and instructors are both provided

    Returns:
        boolean: True if it was assigned, false if it failed
    """
    query = None
    value_type = None
    values = None

    if students and instructors:
        raise ValueError(
            "Can only assign one type of user to a course not both")

    if students:
        value_type = "students"
        query = """
            INSERT INTO course_registration (
                course_id,
                user_id,
                registration_status,
                student_registration_date,
                enroll_date,
                denial_reason,
                user_paid,
                user_paying_cash,
                notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
        """
        values = []
        for student in students:
            values.append((
                course_id,
                student.userId,
                student.registrationStatus,
                datetime.datetime.utcnow(),
                datetime.datetime.utcnow() if student.registrationStatus == "enrolled" else None,
                student.denialReason,
                student.userPaid,
                student.usingCash,
                student.notes
            ))

    if instructors:
        value_type = "instructors"
        query = """
            INSERT INTO course_instructor (
                course_id,
                user_id
            )
            VALUES ($1, $2);
        """
        values = []
        for instructor in instructors:
            values.append((
                course_id,
                instructor
            ))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.executemany(query, values)
        return True

    except Exception:
        log.exception(
            f"An error occured while assigning {value_type} to course_id {course_id}")
    return False


async def assign_bundle(bundle_id: str = None, students: list = None):
    """Function to assign a course to students or instructors

    Args:
        bundle_id (str, optional): Bundle Id to assign to user. Defaults to None.
        students (list, optional): List of students to be assigned to course. Defaults to None.
        instructors (list, optional): List of students to be assigned to course. Defaults to None.

    Raises:
        ValueError: If students and instructors are both provided

    Returns:
        boolean: True if it was assigned, false if it failed
    """
    query = None
    value_type = None
    values = None

    bundle, _ = await get_bundle(bundle_id=bundle_id)
    if not bundle[0]:
        return "user", "Bundle does not exist"

    bundled_courses = []
    for course in bundle["courses"]:
        bundled_courses.append(course["courseId"])

    if students:
        value_type = "students"
        query = """
            INSERT INTO course_registration (
                course_id,
                user_id,
                registration_status,
                student_registration_date,
                enroll_date,
                denial_reason,
                user_paid,
                user_paying_cash,
                notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
        """
        values = []
        for student in students:
            for course_id in bundled_courses:
                values.append((
                    course_id,
                    student.userId,
                    student.registrationStatus,
                    datetime.datetime.utcnow(),
                    datetime.datetime.utcnow() if student.registrationStatus == "enrolled" else None,
                    student.denialReason,
                    student.userPaid,
                    student.usingCash,
                    student.notes
                ))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.executemany(query, values)
        return True

    except Exception:
        log.exception(
            f"An error occured while assigning {value_type} to course_id {course_id}")
    return False


async def find_course_schedule(course_id: str = None) -> list:
    """Function to find a course schedule

    Args:
        course_id (str, optional): Course Id in which is needed to find the schedule. Defaults to None.

    Returns:
        list: List of courses for schedule
    """

    schedule = []
    if not course_id:
        return schedule

    query = """
        SELECT * FROM course_dates where course_id = $1 ORDER BY series_number ASC;
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            occurances = await conn.fetch(query, course_id)
            if occurances:
                for occurance in occurances:
                    schedule.append({
                        "courseId": occurance[0],
                        "courseName": occurance[1],
                        "startDate": str(occurance[2]),
                        "endDate": str(occurance[3]),
                        "duration": occurance[4],
                        "complete": occurance[5]
                    })

    except Exception:
        log.exception(
            f"An error occured while getting schedule for course_id {course_id}")

    return schedule


async def delete_course(course_id: str = None) -> bool:
    """Function to delete a course

    Args:
        course_id (str, optional): Course Id in which needs to be deleted. Defaults to None.

    Returns:
        bool: True if deleted, False if failed
    """
    if not course_id:
        return False

    queries = [
        "DELETE FROM bundled_courses WHERE course_id = $1;",
        "DELETE FROM course_dates WHERE course_id = $1;",
        "DELETE FROM course_instructor WHERE course_id = $1;",
        "DELETE FROM course_registration WHERE course_id = $1;",
        "DELETE FROM courses WHERE course_id = $1;",
        "DELETE FROM prerequisites WHERE course_id = $1;",
        "DELETE FROM course_content WHERE course_id = $1;"
    ]

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            for query in queries:
                await conn.execute(query, course_id)
        return True

    except Exception:
        log.exception(
            f"An error occured while getting schedule for course_id {course_id}")

    return False


async def update_course(content: course_update.UpdateCourseInput):
    """Function to update a course

    Args:
        content (course_update.UpdateCourseInput): Takes in a model of optional args to be updated.

    Returns:
        dict: Returns a course
    """
    try:
        course_id = content.courseId
        instructors = content.instructors
        prerequisites = content.prerequisites
        course = camel_to_snake(content.dict(exclude_unset=True))
        if course.get("enrollable"):
            course["enrollment_start_date"] = datetime.datetime.utcnow()

        del course["enrollable"]
        del course["course_id"]
        del course["instructors"]
        del course["prerequisites"]

        updaters = []
        course_values = [course_id]
        for idx, key in enumerate(list(course.keys())):
            updaters.append(f"{key}=${idx+2}")

        update_query = "UPDATE courses SET {} WHERE course_id = $1;".format(
            ', '.join(updaters))
        course_values.extend(list(course.values()))

        if instructors:
            instructor_update_query = """DELETE FROM course_instructor WHERE course_id = $1;"""
            instructor_update_query_1 = """
                INSERT INTO course_instructor (
                    course_id,
                    user_id
                )
                VALUES ($1, $2);
            """

            instructorValues = []
            for instructor in instructors:
                instructorValues.append([
                    course_id,
                    instructor
                ])

        if prerequisites:
            prerequisites_update_query = """DELETE FROM prerequisites WHERE course_id = $1;"""
            prerequisites_update_query_1 = """
                INSERT INTO prerequisites (
                    course_id,
                    prerequisite
                )
                VALUES ($1, $2);
            """
            prerequisitesValues = []
            for prerequisite in prerequisites:
                prerequisitesValues.append([
                    course_id,
                    prerequisite
                ])

        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(update_query, *course_values)
            if instructors:
                for instructor in instructorValues:
                    await conn.execute(instructor_update_query, instructor[1])
                    await conn.execute(instructor_update_query_1, *instructor)

            if prerequisites:
                for prerequisite in prerequisitesValues:
                    await conn.execute(prerequisites_update_query, prerequisite[0])
                    await conn.execute(prerequisites_update_query_1, *prerequisite)
        return True

    except Exception:
        log.exception("An error occured while updating course")

    return None


async def list_bundles(enrollment: bool = False, page: int = None, pageSize: int = None):
    """Function to list all bundles

    Returns:
        list: A list ofbundles
    """

    listBundles = []

    where_condition = None
    conditions = []

    query = """
    SELECT
    cb.bundle_photo,
    cb.bundle_id,
    cb.bundle_name,
    cb.active,
    cb.is_complete,
    SUM(c.classes_in_series) AS total_classes,
    cb.create_dtm,
    MIN(cd.start_dtm) as start_dtm
    FROM
        course_bundles cb
    JOIN
        bundled_courses bc ON cb.bundle_id = bc.bundle_id
    JOIN
        course_dates cd ON bc.course_id = cd.course_id
    JOIN
        courses c ON bc.course_id = c.course_id
    GROUP BY
        cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
    ORDER BY
        cb.create_dtm DESC;
    """

    if page and pageSize:
        query = """
            SELECT
            cb.bundle_photo,
            cb.bundle_id,
            cb.bundle_name,
            cb.active,
            cb.is_complete,
            SUM(c.classes_in_series) AS total_classes,
            cb.create_dtm,
            MIN(cd.start_dtm) as start_dtm
            FROM
                course_bundles cb
            JOIN
                bundled_courses bc ON cb.bundle_id = bc.bundle_id
            JOIN
                course_dates cd ON bc.course_id = cd.course_id
            JOIN
                courses c ON bc.course_id = c.course_id
            GROUP BY
                cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
            ORDER BY
                cb.create_dtm DESC
            LIMIT $1 OFFSET $2;
        """
    if enrollment:
        conditions.append("cb.active = true")
        conditions.append("cb.is_complete = false")
        conditions.append("(cb.waitlist = true or c.is_full = false)")

    if conditions:
        where_condition = " AND ".join(conditions)
        query = """
            SELECT
            cb.bundle_photo,
            cb.bundle_id,
            cb.bundle_name,
            cb.active,
            cb.is_complete,
            SUM(c.classes_in_series) AS total_classes,
            cb.create_dtm,
            MIN(cd.start_dtm) as start_dtm
            FROM
                course_bundles cb
            JOIN
                bundled_courses bc ON cb.bundle_id = bc.bundle_id
            JOIN
                course_dates cd ON bc.course_id = cd.course_id
            JOIN
                courses c ON bc.course_id = c.course_id
            WHERE {}
            GROUP BY
                cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
            ORDER BY
                cb.create_dtm DESC;
        """.format(where_condition)

        if page and pageSize:
            query = """
                SELECT
                cb.bundle_photo,
                cb.bundle_id,
                cb.bundle_name,
                cb.active,
                cb.is_complete,
                SUM(c.classes_in_series) AS total_classes,
                cb.create_dtm,
                MIN(cd.start_dtm) as start_dtm
                FROM
                    course_bundles cb
                JOIN
                    bundled_courses bc ON cb.bundle_id = bc.bundle_id
                JOIN
                    course_dates cd ON bc.course_id = cd.course_id
                JOIN
                    courses c ON bc.course_id = c.course_id
                WHERE {}
                GROUP BY
                    cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                ORDER BY
                    cb.create_dtm DESC
                LIMIT $1 OFFSET $2;
            """.format(where_condition)

    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                bundles = await conn.fetch(query, pageSize, (page-1)*pageSize)
                if conditions:
                    total_pages = await conn.fetchrow("""
                        SELECT
                        COUNT(*)
                        FROM
                            course_bundles cb
                        JOIN
                            bundled_courses bc ON cb.bundle_id = bc.bundle_id
                        JOIN
                            courses c ON bc.course_id = c.course_id
                        WHERE {}
                        GROUP BY
                            cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                        ORDER BY
                            cb.create_dtm DESC;
                    """.format(where_condition))
                else:
                    total_pages = await conn.fetchrow("""
                        SELECT
                        COUNT(*)
                        FROM
                            course_bundles cb
                        JOIN
                            bundled_courses bc ON cb.bundle_id = bc.bundle_id
                        JOIN
                            courses c ON bc.course_id = c.course_id
                        GROUP BY
                            cb.bundle_id, cb.bundle_name, cb.brief_description, cb.bundle_photo, cb.active, cb.is_complete
                        ORDER BY
                            cb.create_dtm DESC;
                    """)
            else:
                bundles = await conn.fetch(query)

            if bundles:
                for b in bundles:
                    listBundles.append({
                        "bundlePicture": b['bundle_photo'],
                        "bundleId": b['bundle_id'],
                        "bundleName": b['bundle_name'],
                        "active": b['active'],
                        "complete": b['is_complete'],
                        "totalClasses": b['total_classes'],
                        "courseType": "Bundle",
                        "startDate": datetime.datetime.strftime(b['start_dtm'], "%m/%d/%Y %-I:%M %p") if b['start_dtm'] else None,
                    })

    except Exception:
        log.exception("An error occured while getting a course bundle")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return listBundles, int(total_pages)


async def update_bundle(content: bundle_update.UpdateBundleInput):
    """Functiont o update a bundle

    Args:
        content (bundle_update.UpdateBundleInput): Model of optional arguments to be updated in a bundle.

    Returns:
        dict: Returns bundle back
    """

    try:
        courses = content.courseIds
        bundle_id = content.bundleId
        bundle = camel_to_snake(content.dict(exclude_unset=True))
        del bundle["bundle_id"]
        del bundle["course_ids"]

        update_query = "UPDATE course_bundles SET {} WHERE bundle_id = $1".format(
            ', '.join([f"{key} = ${idx+2}" for idx,
                      key in enumerate(list(bundle.keys()))])
        )

        update_values = [bundle_id]
        update_values.extend(list(bundle.values()))

        if courses:
            courses_update_query_1 = """DELETE FROM bundled_courses WHERE course_id = $1;"""
            courses_update_query = """
                INSERT INTO bundled_courses (
                    bundle_id,
                    course_id
                )
                VALUES ($1, $2);
            """

            courseValues = []
            for course_id in courses:
                courseValues.append((
                    bundle_id,
                    course_id
                ))

        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(update_query, *update_values)
            if courses:
                for value in courseValues:
                    await conn.execute(courses_update_query_1, value[0])
                    await conn.execute(courses_update_query, *value)
        return True

    except Exception:
        log.exception("An error occured while updating bundle")

    return None


async def create_course(
        general: create.General,
        user: global_models.User,
        course_id: str,
        classes_in_series: int = 20,
        active: bool = False,
        first_class_dtm: datetime.datetime = None,
        quizzes: list = None,
        surveys: list = None,
        schedule: dict = None,
        frequency: dict = None,
        is_complete: bool = False,
        certificate: bool = False
) -> bool:
    # TODO: Edit the missing doc string values
    """Function to create a course

    Args:
        general (create.General): Model of general info of a course. Course Name, etc.
        schedule (dict): _description_
        frequency (dict): _description_
        user (global_models.User): _description_
        course_id (str): Id of the Course being created
        classes_in_series (int, optional): _description_. Defaults to 20.
        active (bool, optional): _description_. Defaults to False.
        content (list, optional): Any course content, such as images, pdf, etc. Defaults to None.
        first_class_dtm (str, optional): Starting date of the first class. Defaults to None.

    Raises:
        ValueError: If unable to assign instructors to the course

    Returns:
        bool: True if created, False if failed
    """
    courseQuery = """
        INSERT INTO courses (
            course_id,
            course_name,
            brief_description,
            description,
            instruction_types,
            remote_link,
            address,
            max_students,
            classes_in_series,
            class_frequency,
            active,
            enrollment_start_date,
            registration_expiration_dtm,
            create_dtm,
            modify_dtm,
            created_by,
            modified_by,
            auto_student_enrollment,
            waitlist,
            waitlist_limit,
            price,
            allow_cash,
            phone_number,
            languages,
            is_complete,
            is_full,
            first_class_dtm,
            email,
            course_code,
            certificate
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10,
            $11,
            $12,
            $13,
            $14,
            $15,
            $16,
            $17,
            $18,
            $19,
            $20,
            $21,
            $22,
            $23,
            $24,
            $25,
            $26,
            $27,
            $28,
            $29,
            $30
        );
    """

    scheduleValues = []
    prerequisitesValues = []

    if schedule:
        scheduleQuery = """
            INSERT INTO course_dates (
                is_complete,
                course_id,
                series_number,
                start_dtm,
                end_dtm
            ) VALUES ($1, $2, $3, $4, $5);
        """

        for idx, event in enumerate(schedule):
            scheduleValues.append((
                is_complete,
                course_id,
                idx+1,
                event[0].replace(tzinfo=None),
                event[1].replace(tzinfo=None)
            ))

    if general.prerequisites:
        prerequisitesQuery = """
            INSERT INTO prerequisites (
                course_id,
                prerequisite
            ) VALUES ($1, $2);
        """

        if general.prerequisites:
            for prerequisite in general.prerequisites:
                prerequisitesValues.append((
                    course_id,
                    prerequisite
                ))

    formQuery = """
        INSERT INTO course_forms (
            course_id,
            form_id,
            create_dtm,
            modify_dtm,
            available,
            created_by,
            modified_by
        ) VALUES ($1, $2, $3, $4, $5, $6, $7);
    """

    forms = []
    formValues = []
    if quizzes:
        forms.extend(quizzes)
    if surveys:
        forms.extend(surveys)
    if forms:
        for form_id in forms:
            formValues.append((
                course_id,
                form_id,
                datetime.datetime.utcnow(),
                datetime.datetime.utcnow(),
                False,
                user.userId,
                user.userId
            ))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(
                courseQuery,
                course_id,
                general.courseName,
                general.briefDescription if general.briefDescription else None,
                general.description,
                general.instructionTypes,
                general.remoteLink,
                general.address,
                general.maxStudents,
                classes_in_series,
                frequency["frequency_type"],
                active,
                datetime.datetime.utcnow() if general.enrollable else None,
                schedule[0][0].replace(tzinfo=None) -
                datetime.timedelta(hours=8),
                datetime.datetime.utcnow(),
                datetime.datetime.utcnow(),
                user.userId,
                user.userId,
                True if active else False,
                general.waitlist,
                general.waitlistLimit if general.waitlistLimit else general.maxStudents,
                general.price,
                general.allowCash,
                general.phoneNumber,
                general.languages if general.languages else None,
                is_complete,
                False,
                first_class_dtm.replace(tzinfo=None),
                general.email,
                general.courseCode if general.courseCode else None,
                certificate
            )

            if scheduleValues:
                await conn.executemany(scheduleQuery, scheduleValues)

            if prerequisitesValues:
                await conn.executemany(prerequisitesQuery, prerequisitesValues)

            if formValues:
                await conn.executemany(formQuery, formValues)

        if general.instructors:
            assigned = await assign_course(course_id=course_id, instructors=general.instructors)
            if not assigned:
                raise ValueError("Unable to assign instructors to course")

        return True

    except Exception:
        log.exception("An error occured while creating course")

    return False


async def create_bundle(content: bundle.Input, bundle_id: str, user_id: str, is_complete: bool = False):
    """Function to create a bundle

    Args:
        content (bundle.Input): Model of what is being sent to create the bundle with
        bundle_id (str): Bundle Id being used for creation of Bundle
        user_id (str): The user id of which the bundle belongs to

    Returns:
        boolean: True if bundle was created, False if bundle failed
    """

    bundle_query = """
        INSERT INTO course_bundles (
            bundle_id,
            bundle_name,
            active,
            enrollment_start_date,
            registration_expiration_dtm,
            max_students,
            create_dtm,
            modify_dtm,
            created_by,
            modified_by,
            auto_student_enrollment,
            waitlist,
            waitlist_limit,
            price,
            allow_cash,
            is_full,
            is_complete
        ) VALUES (
            $1,
            $2,
            $3,
            $4,
            (
                SELECT
                    MIN(start_dtm)
                FROM course_dates
                WHERE course_id IN ({})
            ),
            $5,
            $6,
            $7,
            $8,
            $9,
            true,
            $10,
            $11,
            $12,
            $13,
            false,
            $14
        );
    """.format(', '.join(['$' + str(i + 15) for i in range(len(content.courseIds))]))

    courses_query = """
        INSERT INTO bundled_courses (
            bundle_id,
            course_id
        ) VALUES ($1, $2);
    """

    values = []
    for course_id in content.courseIds:
        values.append((
            bundle_id,
            course_id
        ))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(
                bundle_query,
                bundle_id,
                content.bundleName,
                content.active,
                datetime.datetime.utcnow() if content.active else None,
                content.maxStudents,
                datetime.datetime.utcnow(),
                datetime.datetime.utcnow(),
                user_id,
                user_id,
                content.waitlist,
                content.maxStudents,
                content.price,
                content.allowCash,
                is_complete,
                *content.courseIds
            )

            if values:
                await conn.executemany(courses_query, values)

        return True

    except Exception:
        log.exception("An error occured while creating course")

    return False


async def get_bundle(bundle_id: str) -> tuple:
    """Function to get a bundle based on a bundle ID

    Args:
        bundle_id (str): Bundle Id to look up, is required

    Returns:
        tuple: Returns a bundle and schedule
    """

    query = """
        SELECT
            c.course_id,
            c.course_name,
            c.brief_description,
            c.instruction_types,
            c.languages,
            b.bundle_name,
            b.bundle_id,
            b.bundle_photo,
            b.price,
            b.active,
            b.max_students,
            b.is_full,
            b.waitlist,
            MAX(cd.start_dtm) as latest_start_dtm,
            b.enrollment_start_date,
            b.registration_expiration_dtm,
            b.allow_cash
        FROM
            course_bundles b
        JOIN
            bundled_courses bc ON bc.bundle_id = b.bundle_id
        JOIN
            courses c ON c.course_id = bc.course_id
        LEFT JOIN
            prerequisites p ON p.bundle_id = b.bundle_id AND p.course_id = c.course_id
        LEFT JOIN
            course_dates cd ON cd.course_id = c.course_id
        WHERE
            b.bundle_id = $1
        GROUP BY
            c.course_id,
            c.course_name,
            c.brief_description,
            c.instruction_types,
            c.languages,
            b.bundle_name,
            b.bundle_id,
            b.bundle_photo,
            b.price,
            b.active,
            b.max_students,
            b.is_full,
            b.waitlist
        ORDER BY
            latest_start_dtm DESC;
    """

    prerequisitesQuery = """
        SELECT
            b.bundle_id,
            b.bundle_name,
            b.brief_description
            FROM course_bundles b
            JOIN prerequisites p
            on b.bundle_id = p.bundle_id
            where p.bundle_id = $1
    """

    scheduleQuery = """
        SELECT
            c.course_name,
            cd.course_id,
            cd.start_dtm,
            cd.end_dtm,
            cd.series_number,
            cd.is_complete
        FROM course_dates cd
        JOIN courses c
        ON c.course_id = cd.course_id
        JOIN bundled_courses bc
        ON cd.course_id = bc.course_id
        WHERE bc.bundle_id = $1
    """
    schedule = []
    bundle = {
        "courses": [],
        "languages": [],
        "instructionTypes": [],
        "prerequisites": []
    }
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found_bundle = await conn.fetch(query, bundle_id)
            found_prerequisites = await conn.fetch(prerequisitesQuery, bundle_id)
            found_schedule = await conn.fetch(scheduleQuery, bundle_id)

            if found_bundle:
                for course in found_bundle:
                    course_info = {
                        "courseId": course['course_id'],
                        "courseName": course['course_name'],
                        "briefDescription": course['brief_description']
                    }
                    bundle["courses"].append(course_info)
                    for instruction_type in course['instruction_types']:
                        if instruction_type not in bundle["instructionTypes"]:
                            bundle["instructionTypes"].append(instruction_type)

                    for lang in course['languages']:
                        if lang not in bundle["languages"]:
                            bundle["languages"].append(lang)

                    bundle.update(
                        {
                            "bundleName": course['bundle_name'],
                            "bundleId": course['bundle_id'],
                            "bundlePicture": course['bundle_photo'],
                            "price": course['price'],
                            "active": course['active'],
                            "maxStudents": course['max_students'],
                            "isFull": course['is_full'],
                            "waitlist": course['waitlist'],
                            "enrollable": (course['latest_start_dtm'] is not None and course['enrollment_start_date'] is not None) and
                                          (course['latest_start_dtm'] <= datetime.datetime.utcnow(
                                          ) <= course['enrollment_start_date']),
                            "allowCash": course['allow_cash']
                        }
                    )

            if found_prerequisites:
                for course in found_prerequisites:
                    bundle["prerequisites"].append({
                        "courseId": course['bundle_id'],
                        "courseName": course['bundle_name'],
                        "briefDescription": course['brief_description']
                    })
            if found_schedule:
                for event in found_schedule:
                    schedule.append({
                        "courseId": event['course_id'],
                        "courseName": event['course_name'],
                        "startTime": event['start_dtm'].strftime("%m/%d/%Y %-I:%M %p"),
                        "duration": (event['end_dtm'] - event['start_dtm']).total_seconds() // 60,
                        "seriesNumber": event['series_number'],
                        "complete": event['is_complete']
                    })
        return (bundle, schedule)

    except Exception:
        log.exception("An error occured while getting a bundle")

    return (None, None)


async def get_total_course_schedule(start_date: str = None, end_date: str = None, page: int = None, pageSize: int = None) -> list:
    """Function to get complete course schedule for all courses

    Args:
        start_date (str, optional): date to start search at. Defaults to None.
        end_date (str, optional): date to end search at. Defaults to None.

    Returns:
        list: List of classes in schedule
    """
    where_condition = None
    schedule = []
    conditions = []
    query = """
        select
            cd.course_id,
            c.course_name,
            cd.start_dtm,
            cd.end_dtm,
            cd.series_number,
            cd.is_complete
        FROM course_dates cd
        JOIN courses c
        on c.course_id = cd.course_id
        ORDER BY start_dtm ASC;
    """

    if page and pageSize:
        query = """
            select
                cd.course_id,
                c.course_name,
                cd.start_dtm,
                cd.end_dtm,
                cd.series_number,
                cd.is_complete
            FROM course_dates cd
            JOIN courses c
            on c.course_id = cd.course_id
            ORDER BY start_dtm ASC
            LIMIT $1 OFFSET $2;
        """
    # TODO: fill these out
    if start_date:
        conditions.append("")

    if end_date:
        conditions.append("")

    if conditions:
        where_condition = " AND ".join(conditions)
        query = """
            select
                cd.course_id,
                c.course_name,
                cd.start_dtm,
                c.duration,
                cd.series_number,
                cd.is_complete
            FROM course_dates cd
            JOIN courses c
            on c.course_id = cd.course_id
            WHERE {}
            ORDER BY start_dtm ASC;
        """.format(where_condition)

        if page and pageSize:
            query = """
                select
                    cd.course_id,
                    c.course_name,
                    cd.start_dtm,
                    c.duration,
                    cd.series_number,
                    cd.is_complete
                FROM course_dates cd
                JOIN courses c
                on c.course_id = cd.course_id
                WHERE {}
                ORDER BY start_dtm ASC
                LIMIT $1 OFFSET $2;
            """.format(where_condition)
    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                found = await conn.fetch(query, pageSize, (page-1)*pageSize)
                total_pages = await conn.fetchrow("""
                    select
                        COUNT(*)
                    FROM course_dates cd
                    JOIN courses c
                    on c.course_id = cd.course_id;
                """)
            else:
                found = await conn.fetch(query)
            if found:
                for event in found:
                    schedule.append({
                        "courseId": event['course_id'],
                        "courseName": event['course_name'],
                        "startTime": event['start_dtm'].strftime("%m/%d/%Y %-I:%M %p"),
                        "duration": (event['end_dtm'] - event['start_dtm']).total_seconds() // 60,
                        "seriesNumber": event['series_number'],
                        "complete": event['is_complete']
                    })

    except Exception:
        log.exception("An error occured while creating course")

    if total_pages:
        total_pages = total_pages[0]/pageSize
    return schedule, int(total_pages)


async def get_content(
    course_id: str = None,
    content_id: str = None,
    published: bool = None,
    page: int = None,
    pageSize: int = None
) -> Union[list, None]:
    """Get content for a course based on Id"""

    conditions = []
    params = []

    if isinstance(published, bool):
        i = len(params) + 1
        conditions.append(f"published = ${i}")
        params.append(published)

    if course_id:
        i = len(params) + 1
        conditions.append(f"course_id = ${i}")
        params.append(course_id)

    if content_id:
        i = len(params) + 1
        conditions.append(f"content_id = ${i}")
        params.append(content_id)

    query = f"""
        SELECT content_name, content_id, published
        FROM course_content
        WHERE {' and '.join(conditions)}
        ORDER BY content_name;
    """

    if page and pageSize:
        i = len(params) + 1
        query.replace(';', f' LIMIT ${i} OFFSET ${i+1};')
        params.extend([pageSize, (page-1)*pageSize])

    content = []
    total_pages = 0

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found = await conn.fetch(query, *params)
            if found:
                for c in found:
                    content.append({
                        "contentName": c['content_name'],
                        "contentId": c['content_id'],
                        "published": c['published']
                    })
                total_pages = await conn.fetchval(f"SELECT COUNT(*) FROM course_content WHERE {' and '.join(conditions)}", *params)
    except Exception:
        log.exception("An error occured while getting course content")

    if total_pages and pageSize:
        total_pages = total_pages / pageSize

    return content, int(total_pages)


async def find_class_time(course_id: str, series_number: int):
    """Function to find class time

    Args:
        course_id (str): Course Id needed to get class time from
        series_number (int): Series Number needed to get class time

    Returns:
        null: Nothing right now?
    """

    found = None
    query = """
        SELECT
            is_complete,
            course_id,
            series_number,
            start_dtm,
            end_dtm,
        FROM course_dates
        WHERE course_id = $1
        AND series_number = $2
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found_class = await conn.fetchrow(query, course_id, series_number)
            if found_class:
                found = {
                    "is_complete": found_class['is_complete'],
                    "course_id": found_class['course_id'],
                    "series_number": found_class['series_number'],
                    "start_dtm": found_class['start_dtm'],
                    "end_dtm": found_class['end_dtm']
                }

    except Exception:
        log.exception("An error occured while getting scheduled class")

    return found


async def update_schedule(new_class: dict):
    """Function to update a schedule

    Args:
        new_class (dict): A dict including the new class being added to the schedule

    Returns:
        bool: True if updated, false if failed
    """

    query = """
        UPDATE course_dates
        SET start_dtm = $1, end_dtm = $2
        WHERE course_id = $3 AND series_number = $4;
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(
                query,
                new_class["start_dtm"].replace(tzinfo=None),
                new_class["end_dtm"].replace(tzinfo=None),
                new_class["course_id"],
                new_class["series_number"]
            )
        return True

    except Exception:
        log.exception("An error occured while getting scheduled class")

    return False


async def validate_prerequisites(course: dict, user_id: str):
    if len(course["prerequisites"]) <= 0:
        return True

    prerequisite_course_ids = [prerequisite['courseId']
                               for prerequisite in course['prerequisites']]

    query = """
    SELECT COUNT(*)
    FROM
        user_certificates
    WHERE
        user_id = $1 AND course_id IN ({})
    """.format(', '.join(['$' + str(i + 2) for i in range(len(prerequisite_course_ids))]))

    count = None
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            count = await conn.fetchrow(query, user_id, *prerequisite_course_ids)

        if count and count != len(prerequisite_course_ids):
            return False

        return True

    except Exception:
        log.exception(
            "An error occured while getting the users certificates for prerequisite validation")

    return False


async def unenroll_user(course_id: str = None, bundle_id: str = None, user_id: str = None) -> bool:

    if course_id:
        value = course_id
        query = """
            DELETE
            FROM course_registration
            WHERE user_id = $1 AND course_id = $2;
        """

    if bundle_id:
        value = bundle_id
        query = """
            DELETE cr FROM course_registration cr
            JOIN bundled_courses bc ON cr.course_id = bc.course_id
            WHERE cr.user_id = $1 AND bc.bundle_id = $2;
        """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, user_id, value)
        return True

    except Exception:
        log.exception("An error occured while removing user from course")

    return False


async def set_course_picture(course_id: str, course_picture: str, user: global_models.User):
    query = """
        UPDATE courses SET
            course_picture=$1,
            modify_dtm=$2,
            modified_by=$3
        WHERE course_id=$4;
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, course_picture, datetime.datetime.utcnow(), user.userId, course_id)
        return True

    except Exception:
        log.exception(
            f"An error occured while updating course picture for course {course_id}")

    return False


async def upload_course_content(course_id: str, content: dict, user: global_models.User):
    contentQuery = """
        INSERT INTO course_content (
            course_id,
            content_name,
            content_id,
            create_dtm,
            modify_dtm,
            created_by,
            modified_by,
            published
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);
    """
    contentValues = []
    if content:
        for i in content:
            contentValues.append((
                course_id,
                i["content_name"],
                i["content_id"],
                datetime.datetime.utcnow(),
                datetime.datetime.utcnow(),
                user.userId,
                user.userId,
                False
            ))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.executemany(contentQuery, contentValues)
        return True

    except Exception:
        log.exception(
            f"An error occured while uploading course content for course {course_id}")

    return False


async def get_course_certificate(course_id: str):
    query = """
        SELECT
            c.certificate_name,
            c.certificate_id,
            c.certificate_length,
            c.certificate_template
        FROM certificate as c
        JOIN course_certificates as cc
        ON c.certificate_id = cc.certificate_id
        WHERE cc.course_id = $1;
    """

    found = {}
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found_certificate = await conn.fetchrow(query, course_id)
            if found_certificate:
                found = {
                    "certificateName": found_certificate['certificate_name'],
                    "certificateId": found_certificate['certificate_id'],
                    "certificateLength": found_certificate['certificate_length'],
                    "certificateTemplate": found_certificate['certificate_template']
                }

    except Exception:
        log.exception(
            f"An error occured while getting certificate for course {course_id}")

    return found


async def publish_content(user_id: str, course_id: str, file_ids: list, publish: bool) -> bool:
    query = """
        UPDATE course_content SET
            published=$1,
            modify_dtm=$2,
            modified_by=$3
        WHERE course_id=$4 and content_id in ({});
    """.format(', '.join(['$' + str(i + 5) for i in range(len(file_ids))]))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, publish, datetime.datetime.utcnow(), user_id, course_id, *file_ids)
        return True

    except Exception:
        log.exception("An error occured while updating course content")

    return False


async def delete_content(file_ids: list, course_id: str = None) -> bool:

    query = """
        DELETE FROM course_content
        WHERE content_id in ({});
    """.format(', '.join(['$' + str(i + 1) for i in range(len(file_ids))]))

    if course_id:
        query = """
            DELETE FROM course_content
            WHERE course_id=$1 and content_id in ({});
        """.format(', '.join(['$' + str(i + 2) for i in range(len(file_ids))]))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if course_id:
                await conn.execute(query, course_id, *file_ids)
            else:
                await conn.execute(query, *file_ids)

        for file_id in file_ids:
            filePath = f"./src/content/users/{file_id}"
            if os.path.exists(filePath):
                os.remove(filePath)

        return True
    except Exception:
        log.exception("An error occured while deleting course content")

    return False


async def create_course_certificate(
    course_id: str,
    certificate_id: str,
    certificate_name: str,
    certificate_length: str,
    certificate_template: str
) -> bool:
    try:
        certificate_query = """
            INSERT INTO certificate (
                certificate_name,
                certificate_id,
                certificate_length,
                certificate_template
            )
            VALUES ($1, $2, $3, $4);
        """

        certificate_course_query = """
            INSERT INTO course_certificates (
                certificate_id,
                course_id
            )
            VALUES ($1, $2)
        """
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(
                certificate_query,
                certificate_name,
                certificate_id,
                certificate_length,
                certificate_template
            )

            await conn.execute(
                certificate_course_query,
                certificate_id,
                course_id
            )

        return True
    except Exception:
        log.exception(f"Failed to create certificate for course {course_id}")
    return False


async def delete_bundle(bundle_id: str) -> bool:
    queries = [
        "DELETE FROM course_bundles where bundle_id = $1;",
        "DELETE FROM prerequisites where bundle_id = $1;",
        "DELETE FROM bundled_courses where bundle_id = $1;"
    ]

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            for query in queries:
                await conn.execute(query, bundle_id)
        return True
    except Exception:
        log.exception(f"Failed to delete bundle {bundle_id}")
    return False


async def mark_class_as_complete(course_id: str, series_number: int = None) -> bool:
    query = """
        UPDATE
            course_dates
        SET
            is_complete=$1
        WHERE
            course_id=$2;
    """

    if series_number:
        query = """
            UPDATE
                course_dates
            SET
                is_complete=$1
            WHERE
                course_id=$2 and series_number=$3;
        """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if series_number:
                await conn.execute(query, True, course_id, series_number)
            else:
                await conn.execute(query, True, course_id)

        return True

    except Exception:
        log.exception(
            f"Failed to mark course classes for {course_id} as complete")

    return False


async def mark_course_as_complete(course_id: str) -> bool:
    query = """
        UPDATE
            courses
        SET
            is_complete=$1
        WHERE
            course_id=$2;
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, True, course_id)

        return True

    except Exception:
        log.exception(
            f"Failed to mark course {course_id} as complete")

    return False


async def mark_bundle_as_complete(bundle_id: str) -> bool:
    query = """
        UPDATE
            course_bundles
        SET
            is_complete=$1
        WHERE
            bundle_id=$2;
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, True, bundle_id)

        return True

    except Exception:
        log.exception(
            f"Failed to mark bundle {bundle_id} as complete")

    return False
