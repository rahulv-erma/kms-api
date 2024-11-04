from typing import Union, List
import datetime
import math
from fractions import Fraction
import os
import asyncpg

from src import log
from src.api.api_models import global_models
from src.api.api_models.users import lookup, my_certifications
from src.database.sql import get_connection, acquire_connection


async def get_user(user_id: str = None, email: str = None, phoneNumber: str = None) -> Union[global_models.User, None]:
    """Function to get a user from postgres database

    Args:
        user_id (str, optional): user_id of the user being looked up. Defaults to None.
        email (str, optional): email of the user being looked up. Defaults to None.
        phoneNumber (str, optional): phone number of the user being looked up. Defaults to None.

    Returns:
        Union[global_models.User, None]: Returns user model or none if nothing is found
    """
    value = None
    query = None
    formatted_user = None

    if user_id:
        value = user_id

        query = """
            select
                user_id,
                first_name,
                middle_name,
                last_name,
                suffix,
                email,
                phone_number,
                dob,
                password,
                time_zone,
                head_shot,
                address,
                city,
                state,
                zipcode,
                eye_color,
                height,
                gender,
                photo_id,
                other_id,
                photo_id_photo,
                other_id_photo,
                active,
                text_notif,
                email_notif,
                expiration_date
            from users
            where user_id = $1;
        """

    if email:
        value = email
        query = """
            select
                user_id,
                first_name,
                middle_name,
                last_name,
                suffix,
                email,
                phone_number,
                dob,
                password,
                time_zone,
                head_shot,
                address,
                city,
                state,
                zipcode,
                eye_color,
                height,
                gender,
                photo_id,
                other_id,
                photo_id_photo,
                other_id_photo,
                active,
                text_notif,
                email_notif,
                expiration_date
            from users
            where email = $1;
        """

    if phoneNumber:
        value = phoneNumber
        query = """
            select
                user_id,
                first_name,
                middle_name,
                last_name,
                suffix,
                email,
                phone_number,
                dob,
                password,
                time_zone,
                head_shot,
                address,
                city,
                state,
                zipcode,
                eye_color,
                height,
                gender,
                photo_id,
                other_id,
                photo_id_photo,
                other_id_photo,
                active,
                text_notif,
                email_notif,
                expiration_date
            from users
            where phone_number = $1;
        """

    if not value and not query:
        return None

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            user = await conn.fetchrow(query, value)
            if user:
                formatted_user = global_models.User(
                    userId=user['user_id'],
                    firstName=user['first_name'],
                    middleName=user['middle_name'],
                    lastName=user['last_name'],
                    suffix=user['suffix'],
                    email=user['email'],
                    phoneNumber=user['phone_number'],
                    eyeColor=user['eye_color'],
                    height={
                        "feet": int(user['height'] // 12),
                        "inches": math.floor(Fraction(round(user['height'] % 12 * 100), 100))
                    } if user['height'] else None,
                    gender=user['gender'],
                    headShot=user['head_shot'],
                    photoId=user['photo_id'],
                    otherId=user['other_id'],
                    photoIdPhoto=user['photo_id_photo'],
                    otherIdPhoto=user['other_id_photo'],
                    password=user['password'],
                    timeZone=user['time_zone'],
                    active=user['active'],
                    textNotifications=user['text_notif'],
                    emailNotifications=user['email_notif'],
                    address=user['address'],
                    city=user['city'],
                    state=user['state'],
                    zipcode=user['zipcode']
                )
                if user['dob']:
                    formatted_user.dob = datetime.datetime.strftime(
                        user['dob'], "%m/%d/%Y")
                if user['expiration_date']:
                    formatted_user.expirationDate = datetime.datetime.strftime(
                        user['expiration_date'], "%m/%d/%Y %-I:%M %p")

    except Exception:
        log.exception(
            f"An error occured while getting the user with identifier {value}")

    return formatted_user


async def create_user(**kwargs) -> bool:
    """Function to create a user
    Args:
        kwargs dict: parameters to use to create user.
    Returns:
        bool: Returns true or false based off of whether user was able to be created or not
    """
    columns = []
    insert_values = []
    for key, value in kwargs['newUser'].items():
        columns.append(key)
        insert_values.append(value)

    query = """
        INSERT INTO users ({})
        VALUES ({});
    """.format(', '.join(columns), ', '.join(['$' + str(i + 1) for i in range(len(insert_values))]))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, *insert_values)
        return True

    except asyncpg.exceptions.UniqueViolationError as err:
        key = err.args[0].split('duplicate key value violates unique constraint "')[
            1].split('"')
        if key == "users_email_key":
            return "Email already exists in LMS"

        if key == "users_phone_number_key":
            return "Phone number already exist in LMS"

        return "User already exists in LMS"

    except Exception:
        log.exception(
            f"An error occured while creating the user with id {kwargs['newUser']['user_id']}")

    return False


async def update_user(user_id: str, **kwargs) -> bool:
    """Function to update a user

    Args:
        email (str): email of the user being updated.
        kwargs dict: parameters to use to update user.

    Returns:
        bool: Returns True or False if user is updated.
    """

    elements = []
    for idx, key in enumerate(kwargs):
        elements.append(f"{key} = ${str(idx+2)}")

    query = "UPDATE users SET {} WHERE user_id = $1".format(
        ', '.join(elements))

    values = [user_id] + list(kwargs.values())
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, *values)

        return True

    except Exception:
        log.exception("An error occured while updating user")

    return None


async def get_user_type(user: lookup.Input, roleName: str, page: int = None, pageSize: int = None) -> Union[list, None]:
    """Function to find student by lookup

    Args:
        student (Input, optional): Parameters to look up a student with. Defaults to None.

    Returns:
        Union[list, None]: Either returns a list of users or none.
    """
    users = []
    where_conditions = []
    values = [roleName]
    if user.firstName:
        where_conditions.append(
            f"UPPER(u.first_name) = UPPER(${len(where_conditions)+2})")
        values.append(user.firstName)
    if user.lastName:
        where_conditions.append(
            f"UPPER(u.last_name) = UPPER(${len(where_conditions)+2})")
        values.append(user.lastName)
    if user._id:
        where_conditions.append(f"u.other_id = ${len(where_conditions)+2}")
        values.append(user._id)

    query = """
        SELECT
            u.head_shot,
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.phone_number,
            u.dob
        FROM users u
        JOIN user_role ur ON u.user_id = ur.user_id
        JOIN roles r ON ur.role_id = r.role_id
        AND r.role_name = $1
        ORDER BY u.last_name;
    """
    if page and pageSize:
        query = """
            SELECT
                u.head_shot,
                u.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone_number,
                u.dob
            FROM users u
            JOIN user_role ur ON u.user_id = ur.user_id
            JOIN roles r ON ur.role_id = r.role_id
            AND r.role_name = $1
            ORDER BY u.last_name
            LIMIT $2 OFFSET $3;
        """
    if where_conditions:
        query = """
            SELECT
                u.head_shot,
                u.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone_number,
                u.dob
            FROM users u
            JOIN user_role ur ON u.user_id = ur.user_id
            JOIN roles r ON ur.role_id = r.role_id
            WHERE {}
            AND r.role_name = $1
            ORDER BY u.last_name;
        """.format(" AND ".join(where_conditions))

        if page and pageSize:
            query = """
                SELECT
                    u.head_shot,
                    u.user_id,
                    u.first_name,
                    u.last_name,
                    u.email,
                    u.phone_number,
                    u.dob
                FROM users u
                JOIN user_role ur ON u.user_id = ur.user_id
                JOIN roles r ON ur.role_id = r.role_id
                WHERE {}
                AND r.role_name = $1
                ORDER BY u.last_name
                LIMIT ${} OFFSET ${};
            """.format(" AND ".join(where_conditions), len(where_conditions)+1, len(where_conditions)+2)

    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                if where_conditions:
                    total_pages = await conn.fetchrow("""
                        SELECT
                            COUNT(*)
                        FROM users u
                        JOIN user_role ur ON u.user_id = ur.user_id
                        JOIN roles r ON ur.role_id = r.role_id
                        WHERE {}
                        AND r.role_name = $1;
                    """.format(
                        " AND ".join(where_conditions)
                    ), *values)
                else:
                    total_pages = await conn.fetchrow("""
                        SELECT
                            COUNT(*)
                        FROM users u
                        JOIN user_role ur ON u.user_id = ur.user_id
                        JOIN roles r ON ur.role_id = r.role_id
                        AND r.role_name = $1;
                    """, *values)
                found = await conn.fetch(query, *values, pageSize, (page-1)*pageSize)
            else:
                found = await conn.fetch(query, *values)

            if found:
                for user in found:
                    users.append({
                        "headShot": user['head_shot'],
                        "userId": user['user_id'],
                        "firstName": user['first_name'],
                        "lastName": user['last_name'],
                        "email": user['email'],
                        "phoneNumber": user['phone_number'],
                        "dob": str(user['dob'])
                    })

    except Exception:
        log.exception("An error occured while getting all users by lookup")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return users, int(total_pages)


async def get_users_for_export(userIds: List[str] = None, role: str = 'student') -> Union[list, None]:
    """Function to get students for export

    Args:
        userIds (List[str], optional): List of student Ids. Defaults to None.

    Returns:
        Union[list, None]: A list of users belonging to whichever role
    """
    users = []
    if not userIds:
        return None

    query = """
        SELECT
            u.user_id,
            u.first_name,
            u.middle_name,
            u.last_name,
            u.suffix,
            u.email,
            u.phone_number,
            u.dob,
            u.eye_color,
            u.height,
            u.photo_id,
            u.other_id,
            u.time_zone,
            u.active,
            u.expiration_date,
            u.text_notif,
            u.email_notif,
            u.address,
            u.city,
            u.state,
            u.zipcode,
            u.gender
        FROM users u
        JOIN user_role ur
        ON ur.user_id = u.user_id
        JOIN roles r
        ON ur.role_id = r.role_id
        WHERE u.user_id IN ({})
        AND r.role_name = $1;
    """.format(', '.join(['$' + str(i + 2) for i in range(len(userIds))]))

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found = await conn.fetch(query, role, *userIds)
            if found:
                for user in found:
                    users.append({
                        "user_id": user['user_id'],
                        "first_name": user['first_name'],
                        "middle_name": user['middle_name'],
                        "last_name": user['last_name'],
                        "suffix": user['suffix'],
                        "email": user['email'],
                        "phone_number": user['phone_number'],
                        "dob": str(user['dob']) if user['dob'] else None,
                        "eye_color": user['eye_color'],
                        "height": (
                            f"feet {int(user['height'] // 12)} inches {math.floor(Fraction(round(user['height'] % 12 * 100), 100))}"
                            if user['height'] else None
                        ),
                        "photo_id": user['photo_id'],
                        "other_id": user['other_id'],
                        "time_zone": user['time_zone'],
                        "active": user['active'],
                        "expiration_date": str(user['expiration_date']) if user['expiration_date'] else None,
                        "text_notif": user['text_notif'],
                        "email_notif": user['email_notif'],
                        "address": user['address'],
                        "city": user['city'],
                        "state": user['state'],
                        "zipcode": user['zipcode'],
                        "gender": user['gender']
                    })

    except Exception:
        log.exception(
            f"An error occured while getting all users for export using {userIds}")

    return users


async def get_user_class(role: str = None, page: int = None, pageSize: int = None) -> Union[list, None]:
    """Function to get all users by a specific role type

    Args:
        role (str, optional): Role to look up. Defaults to None.

    Returns:
        Union[list, None]: List of users or none.
    """
    users = []
    if not role:
        return users
    query = """
        SELECT
            users.head_shot,
            users.user_id,
            users.first_name,
            users.last_name,
            users.email,
            users.phone_number,
            users.dob
        FROM users
        JOIN user_role ON users.user_id = user_role.user_id
        JOIN roles ON user_role.role_id = roles.role_id
        WHERE roles.role_name = $1
        ORDER BY users.last_name;
    """

    if page and pageSize:
        query = """
            SELECT
                users.head_shot,
                users.user_id,
                users.first_name,
                users.last_name,
                users.email,
                users.phone_number,
                users.dob
            FROM users
            JOIN user_role ON users.user_id = user_role.user_id
            JOIN roles ON user_role.role_id = roles.role_id
            WHERE roles.role_name = $1
            ORDER BY users.last_name
            LIMIT $2 OFFSET $3;
        """

    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                found = await conn.fetch(query, role, pageSize, (page-1)*pageSize)
                total_pages = await conn.fetchrow("""
                    SELECT
                        COUNT(*)
                    FROM users
                    JOIN user_role ON users.user_id = user_role.user_id
                    JOIN roles ON user_role.role_id = roles.role_id
                    WHERE roles.role_name = $1;
                """, role)
            else:
                found = await conn.fetch(query, role)
            if found:
                for user in found:
                    users.append({
                        "headShot": user['head_shot'],
                        "userId": user['user_id'],
                        "firstName": user['first_name'],
                        "lastName": user['last_name'],
                        "email": user['email'],
                        "phoneNumber": user['phone_number'],
                        "dob": str(user['dob'])
                    })
    except Exception:
        log.exception(
            f"An error occured while getting the users with role {role}")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return users, int(total_pages)


async def get_user_courses(user_id: str = None, complete: bool = False, page: int = None, pageSize: int = None) -> List[dict]:
    """Function to get a users courses

    Args:
        user_id (str, optional): User Id to look up. Defaults to None.

    Returns:
        List[my_courses.Course]: Returns list of courses in course model
    """
    coursesList = []
    query = """
        SELECT
            c.course_picture,
            c.course_id,
            c.course_name,
            c.brief_description,
            c.classes_in_series,
            c.is_complete
        FROM courses c
        JOIN course_registration cr ON cr.course_id = c.course_id
        WHERE cr.user_id = $1 and c.is_complete = $2;
    """

    if page and pageSize:
        query = """
            SELECT
                c.course_picture,
                c.course_id,
                c.course_name,
                c.brief_description,
                c.classes_in_series,
                c.is_complete
            FROM courses c
            JOIN course_registration cr ON cr.course_id = c.course_id
            WHERE cr.user_id = $1 and c.is_complete = $2
            ORDER BY c.course_name
            LIMIT $3 OFFSET $4;
        """
    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if pageSize and page:
                courses = await conn.fetch(query, user_id, complete, pageSize, (page-1)*pageSize)
                total_pages = await conn.fetchrow("""
                    SELECT COUNT(*)
                    FROM courses c
                    JOIN course_registration cr ON cr.course_id = c.course_id
                    WHERE cr.user_id = $1 and c.is_complete = $2
                """, user_id, complete)
            else:
                courses = await conn.fetch(query, user_id, complete)

            if courses:
                for course in courses:
                    coursesList.append({
                        "coursePicture": course['course_picture'],
                        "courseId": course['course_id'],
                        "courseName": course['course_name'],
                        "briefDescription": course['brief_description'],
                        "totalClasses": course['classes_in_series'],
                        "courseType": "Course",
                        "complete": course['is_complete']
                    })

    except Exception:
        log.exception(
            f"An error occured while getting courses related to {user_id}")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return coursesList, int(total_pages)


async def get_roles(page: int = None, pageSize: int = None) -> Union[List[dict], None]:
    """Function to get roles

    Returns:
        Union[List[Role], list]: returns list of roles or empty list.
    """
    query = None
    query = """
        select role_id, role_name, role_desc from roles order by role_name;
    """
    if page and pageSize:
        query = """
            select role_id, role_name, role_desc from roles order by role_name LIMIT $1 OFFSET $2;
        """
    total_pages = 0
    roles = []
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                found_roles = await conn.fetch(query, pageSize, pageSize*page)
                total_pages = await conn.fetchrow("SELECT COUNT(*) FROM roles")
            found_roles = await conn.fetch(query)
            if found_roles:
                for role in found_roles:
                    roles.append({
                        "roleId": role['role_id'],
                        "roleName": role['role_name'],
                        "description": role['role_desc']
                    })

    except Exception:
        log.exception("An error occured while getting role list")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return roles, int(total_pages)


async def get_course_students(course_id: str = None, bundle_id: str = None) -> list:
    """Function to get a courses students

    Args:
        course_id (str, optional): course id of the course looked up. Defaults to None.
        student_details (bool, optional): Bool to depict whether student details are needed. Defaults to False.

    Returns:
        list: _description_
    """
    students = []
    if not course_id:
        return students

    if course_id:
        value = course_id
        query = """
            SELECT DISTINCT
                stu.head_shot,
                stu.user_id,
                stu.first_name,
                stu.last_name,
                stu.dob,
                cr.user_paid,
                cr.user_paying_cash,
                cr.registration_status,
                cr.notes
            FROM users AS stu
            JOIN course_registration AS cr ON stu.user_id = cr.user_id
            LEFT JOIN user_certificates AS uc ON stu.user_id = uc.user_id AND cr.course_id = uc.course_id
            WHERE cr.course_id = $1
            GROUP BY
                stu.user_id,
                cr.registration_status,
                cr.user_paid,
                cr.user_paying_cash,
                uc.course_id,
                cr.notes;
        """

    if bundle_id:
        value = bundle_id
        query = """
            SELECT DISTINCT
                stu.head_shot,
                stu.user_id,
                stu.firstName,
                stu.lastName,
                stu.dob,
                cr.user_paid,
                cr.user_paying_cash,
                cr.registration_status,
                cr.notes
            FROM bundled_courses AS bc
            JOIN course_registration AS cr
            ON cr.course_id = bc.course_id
            JOIN users as stu
            ON stu.user_id = cr.user_id
            WHERE bc.bundle_id = $1;
        """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found_students = await conn.fetch(query, value)
            if found_students:
                for student in found_students:
                    students.append({
                        "headShot": student['head_shot'],
                        "userId": student['user_id'],
                        "firstName": student['first_name'],
                        "lastName": student['last_name'],
                        "dob": str(student['dob']),
                        "paid": student['user_paid'],
                        "usingCash": student['user_paying_cash'],
                        "enrollmentStatus": student['registration_status'],
                        "notes": student["notes"]
                    })

    except Exception:
        log.exception(
            f"An error occured while getting students for course_id {course_id}")

    return students


async def manage_user_roles(roles: list = None, user_id: str = None, action: str = "add") -> bool:
    """Function to manage a users roles

    Args:
        roles (list, optional): list of roles to add/remove. Defaults to None.
        user_id (str, optional): user id of the user editing. Defaults to None.
        action (str, optional): action to add or remove roles. Defaults to "add".

    Raises:
        ValueError: _description_
        ValueError: _description_

    Returns:
        bool: _description_
    """
    if not roles or not user_id:
        return False

    if action not in ("add", "remove"):
        raise ValueError("Invalid action specified. Use 'add' or 'remove'.")

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            for role in roles:
                role_id = await get_role_id(role_name=role)
                if action == "add":
                    query = """
                        INSERT INTO user_role
                        (user_id, role_id)
                        VALUES ($1, $2);
                    """
                elif action == "remove":
                    query = """
                        DELETE FROM user_role
                        WHERE user_id = $1
                        AND role_id = $2;
                    """
                else:
                    raise ValueError("Invalid action specified")

                await conn.execute(query, user_id, role_id)

        return True

    except Exception:
        log.exception(
            f"An error occured while assigning role {role_id} to user {user_id}")

    return False


async def get_user_roles(user_id: str = None) -> list:
    """Function to get a users roles

    Args:
        user_id (str, optional): user id of the user. Defaults to None.

    Returns:
        list: list of roles for the user
    """
    roles = []
    if not user_id:
        return roles

    query = """
        SELECT r.*
        from roles as r
        JOIN user_role as ur
        ON ur.role_id = r.role_id
        WHERE ur.user_id = $1 AND r.active = true;
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found_roles = await conn.fetch(query, user_id)
            for role in found_roles:
                roles.append({
                    "roleId": role[0],
                    "roleName": role[1],
                    "roleDesc": role[2]
                })

    except Exception:
        log.exception(
            f"An error occured while getting roles for user {user_id}")

    return roles


async def get_role_id(role_name: str = None) -> str:
    """Functon to get a role's role_id

    Args:
        role_name (str, optional): role name of the role being looked up. Defaults to None.

    Returns:
        str: Returns the role Id of the role
    """
    query = """
    SELECT role_id from roles where role_name = $1
    """
    role_id = None
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            found_role_id = await conn.fetchrow(query, role_name)
            if found_role_id:
                role_id = found_role_id['role_id']

    except Exception:
        log.exception(
            f"An error occured while getting role_id for role {role_name}")

    return role_id


async def get_students(course_id: str = None, bundle_id: str = None) -> list:
    """function to get students for a course

    Args:
        course_id (str): course id to get students

    Returns:
        list: students of the course id provided
    """
    value = course_id
    query = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.phone_number,
            u.text_notif,
            u.email_notif
        FROM users u
        JOIN course_registration cr
        on u.user_id = cr.user_id
        WHERE cr.course_id = $1;
    """

    if bundle_id:
        value = bundle_id
        query = """
            SELECT
                u.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone_number,
                u.text_notif,
                u.email_notif
            FROM users u
            JOIN course_registration cr
            on u.user_id = cr.user_id
            JOIN bundled_courses bc
            on cr.course_id = bc.course_id
            JOIN course_bundles b
            ON bc.bundle_id = b.bundle_id
            WHERE b.bundle_id = $1;
        """
    formatted_students = []
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            students = await conn.fetch(query, value)
            if students:
                for student in students:
                    formatted_students.append({
                        "user_id": student['user_id'],
                        "first_name": student['first_name'],
                        "last_name": student['last_name'],
                        "email": student['email'],
                        "phone_number": student['phone_number'],
                        "email_allowed": student['email_notif'],
                        "text_allowed": student['text_notif']
                    })

    except Exception:
        log.exception(
            f"An error occured while getting students for course {course_id}")

    return formatted_students


async def get_instructors(course_id: str = None, bundle_id: str = None) -> list:
    """function to get instructors of a course

    Args:
        course_id (str): id of the course to check

    Returns:
        list: list of instructors
    """

    if course_id:
        value = course_id
        query = """
            SELECT
                u.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone_number,
                u.text_notif,
                u.email_notif
            FROM users u
            JOIN course_instructor ci
            on u.user_id = ci.user_id
            WHERE ci.course_id = $1;
        """
    if bundle_id:
        value = bundle_id
        query = """
            SELECT
                u.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone_number,
                u.text_notif,
                u.email_notif
            FROM users u
            JOIN course_instructor ci
            on u.user_id = ci.user_id
            JOIN bundled_courses bc
            on cr.course_id = bc.course_id
            JOIN course_bundles b
            ON bc.bundle_id = b.bundle_id
            WHERE b.bundle_id = $1;
        """
    formatted_instructors = []
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            instructors = await conn.fetch(query, value)
            if instructors:
                for instructor in instructors:
                    formatted_instructors.append({
                        "user_id": instructor['user_id'],
                        "first_name": instructor['first_name'],
                        "last_name": instructor['last_name'],
                        "email": instructor['email'],
                        "phone_number": instructor['phone_number'],
                        "email_allowed": instructor['text_notif'],
                        "text_allowed": instructor['email_notif']
                    })
    except Exception:
        log.exception(
            f"Failed to get course instructors for course_id {course_id}")
    return formatted_instructors


async def get_user_certifications(user_id: str, certificate_number: str = None, page: int = None, pageSize: int = None):
    query = """
        SELECT
            uc.user_id,
            c.course_code,
            c.course_name,
            COALESCE(cert.certificate_name, uc.certificate_name) as certificate_name,
            uc.certificate_number,
            uc.completion_date,
            uc.expiration_date,
            u.first_name as student_first,
            u.last_name as student_last,
            inst.first_name as instr_first,
            inst.last_name as instr_last
        FROM user_certificates as uc
        LEFT JOIN courses as c
        ON c.course_id = uc.course_id
        LEFT JOIN certificate cert
        ON uc.certificate_id = cert.certificate_id
        LEFT JOIN users as u
        ON u.user_id = uc.user_id
        LEFT JOIN users as inst
        ON uc.instructor_id = inst.user_id
        WHERE
            uc.user_id = $1
        ORDER BY uc.completion_date;
    """
    if page and pageSize:
        query = """
            SELECT
                uc.user_id,
                c.course_code,
                c.course_name,
                COALESCE(cert.certificate_name, uc.certificate_name) as certificate_name,
                uc.certificate_number,
                uc.completion_date,
                uc.expiration_date,
                u.first_name as student_first,
                u.last_name as student_last,
                inst.first_name as instr_first,
                inst.last_name as instr_last
            FROM user_certificates as uc
            LEFT JOIN courses as c
            ON c.course_id = uc.course_id
            LEFT JOIN certificate cert
            ON uc.certificate_id = cert.certificate_id
            LEFT JOIN users as u
            ON u.user_id = uc.user_id
            LEFT JOIN users as inst
            ON uc.instructor_id = inst.user_id
            WHERE
                uc.user_id = $1
            ORDER BY uc.completion_date
            LIMIT $2 OFFSET $3;
        """
    if certificate_number and page and pageSize:
        query = """
            SELECT
                uc.user_id,
                c.course_code,
                c.course_name,
                COALESCE(cert.certificate_name, uc.certificate_name) as certificate_name,
                uc.certificate_number,
                uc.completion_date,
                uc.expiration_date,
                u.first_name as student_first,
                u.last_name as student_last,
                inst.first_name as instr_first,
                inst.last_name as instr_last
            FROM user_certificates as uc
            LEFT JOIN courses as c
            ON c.course_id = uc.course_id
            LEFT JOIN certificate cert
            ON uc.certificate_id = cert.certificate_id
            LEFT JOIN users as u
            ON u.user_id = uc.user_id
            LEFT JOIN users as inst
            ON uc.instructor_id = inst.user_id
            WHERE
                uc.user_id = $1 and uc.certificate_number = $2
            ORDER BY uc.completion_date
            LIMIT $3 OFFSET $4;
        """
    if certificate_number:
        query = """
            SELECT
                uc.user_id,
                c.course_code,
                c.course_name,
                COALESCE(cert.certificate_name, uc.certificate_name) as certificate_name,
                uc.certificate_number,
                uc.completion_date,
                uc.expiration_date,
                u.first_name as student_first,
                u.last_name as student_last,
                inst.first_name as instr_first,
                inst.last_name as instr_last
            FROM user_certificates as uc
            LEFT JOIN courses as c
            ON c.course_id = uc.course_id
            LEFT JOIN certificate cert
            ON uc.certificate_id = cert.certificate_id
            LEFT JOIN users as u
            ON u.user_id = uc.user_id
            LEFT JOIN users as inst
            ON uc.instructor_id = inst.user_id
            WHERE
                uc.user_id = $1 and uc.certificate_number = $2
            ORDER BY uc.completion_date
        """
    certifications = []

    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if certificate_number:
                if pageSize and page:
                    certificates = await conn.fetch(query, user_id, certificate_number, pageSize, (page-1)*pageSize)
                    total_pages = await conn.fetchrow("""
                        SELECT COUNT(*)
                        FROM user_certificates as uc
                        LEFT JOIN courses as c
                        ON c.course_id = uc.course_id
                        LEFT JOIN certificate cert
                        ON uc.certificate_id = cert.certificate_id
                        LEFT JOIN users as u
                        ON u.user_id = uc.user_id
                        LEFT JOIN users as inst
                        ON uc.instructor_id = inst.user_id
                        WHERE
                            uc.user_id = $1 and uc.certificate_number = $2;
                    """, user_id, certificate_number)
                else:
                    certificates = await conn.fetch(query, user_id, certificate_number)
            else:
                if pageSize and page:
                    certificates = await conn.fetch(query, user_id, pageSize, (page-1)*pageSize)
                    total_pages = await conn.fetchrow("""
                        SELECT
                            COUNT(*)
                        FROM user_certificates as uc
                        LEFT JOIN courses as c
                        ON c.course_id = uc.course_id
                        LEFT JOIN certificate cert
                        ON uc.certificate_id = cert.certificate_id
                        LEFT JOIN users as u
                        ON u.user_id = uc.user_id
                        LEFT JOIN users as inst
                        ON uc.instructor_id = inst.user_id
                        WHERE
                            uc.user_id = $1;
                    """, user_id)
                else:
                    certificates = await conn.fetch(query, user_id)
            if certificates:
                for c in certificates:
                    certificate_name = []
                    if c['certificate_name']:
                        certificate_name.append(c['certificate_name'])
                    else:
                        if c['course_name']:
                            certificate_name.append(c['course_name'])
                        if c['course_code']:
                            certificate_name.append(c['course_code'])

                    certificate = my_certifications.Certification(
                        userId=c['user_id'],
                        certificateName=', '.join(
                            certificate_name) if certificate_name else "N/A",
                        certificateNumber=c['certificate_number'],
                        completionDate=datetime.datetime.strftime(
                            c['completion_date'], "%m/%d/%Y %-I:%M %p") if c['completion_date'] else None,
                        expirationDate=datetime.datetime.strftime(
                            c['expiration_date'], "%m/%d/%Y %-I:%M %p") if c['expiration_date'] else None,
                        student=f"{c['student_first']} {c['student_last']}",
                        instructor=f"{c['instr_first']} {c['instr_last']}" if c['instr_first'] and c['instr_last'] else os.getenv(
                            "COMPANY_NAME")
                    )
                    certifications.append(certificate.dict())

    except Exception:
        log.exception(
            f"An error occured while getting certifications for user {user_id}")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return certifications, int(total_pages)


async def upload_user_pictures(user_id: str, save_to_db: dict, user: global_models.User):
    set_conditions = ["modify_dtm = $1"]
    params = [datetime.datetime.utcnow()]
    param_counter = 2
    if save_to_db.get("head_shot"):
        set_conditions.append(f"head_shot = ${param_counter}")
        params.append(save_to_db["head_shot"])
        param_counter += 1
    if save_to_db.get("photo_id_photo"):
        set_conditions.append(f"photo_id_photo = ${param_counter}")
        params.append(save_to_db["photo_id_photo"])
        param_counter += 1
    if save_to_db.get("other_id_photo"):
        set_conditions.append(f"other_id_photo = ${param_counter}")
        params.append(save_to_db["other_id_photo"])
        param_counter += 1

    query = f"""
        UPDATE users SET {', '.join(set_conditions)}
        WHERE user_id=${param_counter};
    """
    params.append(user_id)

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, *params)
        return True

    except Exception:
        log.exception(
            f"An error occured while updating user picture for user {user_id}")

    return False


async def delete_users(user_ids: list) -> tuple:
    failed_deletes = []
    err = None
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            for user_id in user_ids:
                try:
                    user = await get_user(user_id=user_id)
                    if not user:
                        log.error(f"user not found for user_id {user_id}")
                        failed_deletes.append({
                            "userId": user_id,
                            "reason": "Failed to find user"
                        })
                        continue
                    async with conn.transaction():
                        await conn.execute("DELETE FROM user_role WHERE user_id = $1", user_id)
                        await conn.execute("DELETE FROM course_instructor WHERE user_id = $1", user_id)
                        await conn.execute("DELETE FROM course_registration WHERE user_id = $1", user_id)
                        await conn.execute("DELETE FROM form_submissions WHERE user_id = $1", user_id)
                        await conn.execute("DELETE FROM user_certificates WHERE user_id = $1", user_id)
                        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)

                    if user.headShot:
                        filePath = f"./src/content/users/{user.headShot}"
                        if os.path.exists(filePath):
                            os.remove(filePath)

                    if user.otherIdPhoto:
                        filePath = f"./src/content/users/{user.otherIdPhoto}"
                        if os.path.exists(filePath):
                            os.remove(filePath)

                    if user.photoIdPhoto:
                        filePath = f"./src/content/users/{user.photoIdPhoto}"
                        if os.path.exists(filePath):
                            os.remove(filePath)

                except Exception:
                    log.exception("Failed to delete something")
                    failed_deletes.append({
                        "userId": user_id,
                        "reason": "Failed to delete specific user"
                    })
    except Exception:
        log.exception("An exception occured while deleting users")
        err = "Fatal error occured"

    return (failed_deletes if failed_deletes else None, err)


async def deactivate_user(user_id: str) -> Union[bool, str]:
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute("""UPDATE users SET active=false WHERE user_id = $1""", user_id)
        return True
    except Exception:
        log.exception(
            f"An exception occured while deactivating user {user_id}")
    return False


async def activate_user(user_id: str) -> Union[bool, str]:
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(
                """UPDATE users SET active=true WHERE user_id = $1""", user_id)
        return True
    except Exception:
        log.exception(f"An exception occured while activating user {user_id}")
    return False


async def get_certificates(page: int = None, pageSize: int = None) -> list:
    """Function to get all user certifications

    Returns:
        list: List of user certifications
    """
    formatted_certifications = []
    found_certificates = None
    query = """
        SELECT
            u.user_id,
            u.head_shot,
            u.first_name,
            u.last_name,
            uc.certificate_number,
            uc.completion_date,
            uc.expiration_date,
            cert.certificate_name,
            c.course_name,
            c.course_code
        FROM users u
        JOIN user_certificates uc
        ON u.user_id = uc.user_id
        JOIN courses c
        ON c.course_id = uc.course_id
        LEFT JOIN certificate cert
        ON uc.certificate_id = cert.certificate_id
        ORDER BY u.last_name;
    """

    if page and pageSize:
        query = """
            SELECT
                u.user_id,
                u.head_shot,
                u.first_name,
                u.last_name,
                uc.certificate_number,
                uc.completion_date,
                uc.expiration_date,
                cert.certificate_name,
                c.course_name,
                c.course_code
            FROM users u
            JOIN user_certificates uc
            ON u.user_id = uc.user_id
            JOIN courses c
            ON c.course_id = uc.course_id
            LEFT JOIN certificate cert
            ON uc.certificate_id = cert.certificate_id
            ORDER BY u.last_name
            LIMIT $1 OFFSET $2;
        """

    total_pages = 0
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if page and pageSize:
                total_pages = await conn.fetchrow("""
                    SELECT
                        COUNT(*)
                    user_certificates;
                """)
                found_certificates = await conn.fetch(query, pageSize, (page-1)*pageSize)
            else:
                found_certificates = await conn.fetch(query)

        if found_certificates:
            for cert in found_certificates:
                certificate_name = cert.get("certificate_name")
                if not certificate_name:
                    certificate_name = ""
                    if cert["course_code"]:
                        certificate_name += f"{cert['course_code']} "
                    if cert["course_name"]:
                        certificate_name += cert["course_name"]

                formatted_certifications.append({
                    "userId": cert['user_id'],
                    "headShot": cert['head_shot'],
                    "firstName": cert['first_name'],
                    "lastName": cert['last_name'],
                    "certificateNumber": cert['certificate_number'],
                    "certificateName": certificate_name,
                    "completionDate": datetime.datetime.strftime(cert['completion_date'], "%m/%d/%Y %-I:%M %p") if cert['completion_date'] else None,
                    "expirationDate": datetime.datetime.strftime(cert['expiration_date'], "%m/%d/%Y %-I:%M %p") if cert['expiration_date'] else None
                })
    except Exception:
        log.exception("Failed to get certifications")

    if total_pages:
        total_pages = total_pages[0]/pageSize

    return formatted_certifications, int(total_pages)


async def delete_user_certificates(certificate_numbers: list) -> bool:
    query = """
        DELETE FROM user_certificates where certificate_number = $1
    """

    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            for certificate_number in certificate_numbers:
                await conn.execute(query, certificate_number)
        return True

    except Exception:
        log.exception(f"Failed to delete certificate {certificate_number}")

    return False


async def find_certificate(user_id: str, course_id: str = None, certificate_name: str = None):
    query = """
    SELECT * FROM user_certificates WHERE user_id = $1 AND certificate_name = $2;
    """

    if course_id:
        query = """
        SELECT * FROM user_certificates WHERE user_id = $1 AND course_id = $2;
        """

    found = None
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            if course_id:
                found = await conn.fetch(query, user_id, course_id)
            else:
                found = await conn.fetch(query, user_id, certificate_name)

        if found:
            return True

    except Exception:
        log.exception("Failed to find user certificates")

    return False
