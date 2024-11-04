import json
import os
import pytz
import datetime
import io
from zipfile import ZipFile

from src import log
from src.api.api_models.global_models import User
from src.database.sql.course_functions import get_course, get_bundle
from src.utils.mailer import send_email, class_calendar_invite
from src.utils.generate_random_code import generate_random_code


def load_template(location: str):
    data = None
    try:
        with open(location) as file:
            data = json.load(file)
    except Exception:
        log.exception("failed to load template")
    return data


def self_register_notification(user: User) -> bool:
    try:
        template = load_template(
            "/source/src/content/templates/register/self_register.json")
        if not template:
            raise Exception("Failed to load template")
        if user.textNotifications:
            # TODO: send text confirmation
            pass
        if user.emailNotifications:
            template = {
                "subject": template["email"]["subject"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName
                ),
                "body": template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_url=os.getenv("COMPANY_URL", 'doitsolutions.io'),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io")
                )
            }

            tries = 0
            while True:
                try:
                    email = send_email(
                        receiver=[user.email],
                        email_content=template
                    )
                    if email:
                        break
                except Exception:
                    log.error(f"Attempting to resend email to {email}")
                    if tries >= 5:
                        log.exception(
                            f"Failed to send email to user email {user.email}")
                tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify new user on registration {user}")
    return False

# TODO: test notification


def user_register_notification(user: User) -> bool:
    try:
        template = load_template(
            "/source/src/content/templates/register/user_register.json")
        if not template:
            raise Exception("Failed to load template")
        if user.textNotifications:
            # TODO: send text confirmation
            pass
        if user.emailNotifications:
            template = {
                "subject": template["email"]["subject"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName
                ),
                "body": template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_url=os.getenv("COMPANY_URL", 'doitsolutions.io'),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                    user_email=user.email,
                    user_password=user.password
                )
            }
            tries = 0
            while True:
                try:
                    email = send_email(
                        receiver=[user.email],
                        email_content=template
                    )
                    if email:
                        break
                except Exception:
                    log.error(f"Attempting to resend email to {email}")
                    if tries >= 5:
                        log.exception(
                            f"Failed to send email to user email {user.email}")
                tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on registration {user}")
    return False


def certification_failed_users_notification(email: str, failed_users: list, actual_amount: int, temp_files: list, file_name: str):
    try:
        template = load_template(
            "/source/src/content/templates/training_connect/certificate_failed_users.json")
        if not template:
            raise Exception("Failed to load template")

        failed_users_list = "<ul>"
        for u in failed_users:
            course_name = str(u['user']['course_name']).replace(
                "&amp;", "").replace("&nbsp;", "")
            failed_users_list += (f"<li>{u['user']['first_name']} {u['user']['last_name']} for {course_name}<ul><li>Reason: " +
                                  f"{u['reason']}</li></ul></li>")
        failed_users_list += "</ul>"

        zip_buffer = io.BytesIO()

        with ZipFile(zip_buffer, 'w') as zipf:
            for i, file in enumerate(temp_files):
                full_name = str(file['user']['first_name']) + \
                    " " + str(file['user']['last_name'])
                random = generate_random_code(4)
                zipf.writestr(f'{full_name}_{random}.png', file['tempfile'])

        template = {
            "subject": template["email"]["subject"].format(
                company_name=os.getenv("COMPANY_NAME", "ABC Safety Group")
            ),
            "body": template["email"]["body"].format(
                company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                company_phone=os.getenv("COMPANY_PHONE", "1234"),
                company_url=os.getenv("COMPANY_URL", 'doitsolutions.io'),
                company_email=os.getenv(
                    "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                email=email,
                failed_users=failed_users_list,
                failed_amount=str(len(failed_users)),
                failed_users_text="Failed Users:" if temp_files else "",
                file_name=file_name
            )
        }

        if temp_files:
            template['attachments'] = [zip_buffer]

        tries = 0
        while True:
            try:
                e = send_email(
                    receiver=[email],
                    email_content=template
                )

                if e:
                    break
            except Exception:
                log.error(f"Attempting to resend email to {email}")
                if tries >= 5:
                    log.exception(
                        f"Failed to send email to user email {email}")
            tries += 1
        return True
    except Exception:
        log.exception(f"Failed to send failed users to {email}")
    return False


def student_failed_users_notification(email: str, failed_users: list, file_name: str = None):
    try:
        template = load_template(
            "/source/src/content/templates/training_connect/student_failed_users.json")
        if not template:
            raise Exception("Failed to load template")

        failed_users_list = "<ul>"
        for u in failed_users:
            failed_users_list += (f"<li>{u['user'].get('first_name', 'None provided')} {u['user'].get('last_name', 'None Provided')}" +
                                  f"<ul><li>Reason: {u.get('reason', 'Please upload manually')}</li></ul></li>")
        failed_users_list += "</ul>"

        template = {
            "subject": template["email"]["subject"].format(
                company_name=os.getenv("COMPANY_NAME", "ABC Safety Group")
            ),
            "body": template["email"]["body"].format(
                company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                company_phone=os.getenv("COMPANY_PHONE", "1234"),
                company_url=os.getenv("COMPANY_URL", 'doitsolutions.io'),
                company_email=os.getenv(
                    "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                email=email,
                failed_users=failed_users_list,
                failed_amount=str(len(failed_users)),
                file_name=file_name if file_name else "'no file name provided'",
                failed_users_text="Failed Users:" if failed_users_list else ""
            )
        }

        tries = 0
        while True:
            try:
                e = send_email(
                    receiver=[email],
                    email_content=template
                )

                if e:
                    break
            except Exception:
                log.error(f"Attempting to resend email to {email}")
                if tries >= 5:
                    log.exception(
                        f"Failed to send email to user email {email}")
            tries += 1
        return True
    except Exception:
        log.exception(f"Failed to send failed users to {email}")
    return False

# TODO: test notification


def password_reset_notification(user: User, code: str) -> bool:
    try:
        template = load_template(
            "/source/src/content/templates/password_reset/password_reset.json")
        if not template:
            raise Exception("Failed to load template")
        if user.textNotifications:
            # TODO: send text confirmation
            pass
        if user.emailNotifications:
            template = {
                "subject": template["email"]["subject"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group")
                ),
                "body": template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_url=os.getenv("COMPANY_URL", 'doitsolutions.io'),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                    reset_link=str(
                        os.getenv("COMPANY_URL", 'doitsolutions.io')) + f"/forgot-password?code={code}"
                )
            }
            tries = 0
            while True:
                try:
                    email = send_email(
                        receiver=[user.email],
                        email_content=template
                    )
                    if email:
                        break
                except Exception:
                    log.error(f"Attempting to resend email to {email}")
                    if tries >= 5:
                        log.exception(
                            f"Failed to send email to user email {user.email}")
                tries += 1
        return True
    except Exception:
        log.exception(f"Failed to send a password reset to user {user}")
    return False


# TODO: test notification
async def instructor_enroll_notification(users: list, course_id: str):
    try:
        # TODO: need to make template
        template = load_template(
            "/source/src/content/templates/course_enroll/instructor_enroll.json")
        course = await get_course(course_id)
        if not course[0]:
            raise Exception("Failed to get course")
        if not template:
            raise Exception("Failed to load template")
        text_users = []
        email_users = []
        for user in users:
            if user.textNotifications:
                text_users.append(user)
            if user.emailNotifications:
                email_users.append(user)
        if text_users:
            for user in text_users:
                continue
            # TODO: send text confirmation
            pass
        if email_users:
            for user in email_users:
                template = {
                    "subject": template["email"]["subject"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName
                    ),
                    "body": template["email"]["body"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName,
                        company_phone=os.getenv("COMPANY_PHONE", "1234"),
                        company_url=os.getenv(
                            "COMPANY_URL", 'doitsolutions.io'),
                        company_email=os.getenv(
                            "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                        course_name=course[0]["courseName"],
                        first_class_dtm=course[0]["startDate"]
                    )
                }
                tries = 0
                while True:
                    try:
                        email = send_email(
                            receiver=[user.email],
                            email_content=template
                        )
                        if email:
                            break
                    except Exception:
                        log.error(f"Attempting to resend email to {email}")
                        if tries >= 5:
                            log.exception(
                                f"Failed to send email to user email {user.email}")
                    tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on registration {user}")
    return False

# TODO: test notification


async def student_enroll_notification(users: list, course_id: str):
    try:
        # TODO: need to make template
        template = load_template(
            "/source/src/content/templates/course_enroll/student_enroll.json")
        course = await get_course(course_id)
        if not course[0]:
            raise Exception("Failed to get course")
        if not template:
            raise Exception("Failed to load template")
        text_users = []
        email_users = []
        for user in users:
            if user.textNotifications:
                text_users.append(user)
            if user.emailNotifications:
                email_users.append(user)
        instructors = []
        if course[0]['instructors']:
            for instructor in course[0]['instructors']:
                instructors.append(
                    f"{instructor['firstName']} {instructor['lastName']}")
        if text_users:
            for user in text_users:
                continue
            # TODO: send text confirmation
            pass
        if email_users:
            for user in email_users:
                template = {
                    "subject": template["email"]["subject"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName
                    ),
                    "body": template["email"]["body"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName,
                        company_phone=os.getenv("COMPANY_PHONE", "1234"),
                        company_url=os.getenv(
                            "COMPANY_URL", 'doitsolutions.io'),
                        company_email=os.getenv(
                            "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                        course_name=course[0]["courseName"],
                        first_class_dtm=course[0]["startDate"],
                        instructors=', '.join(
                            instructors) if instructors else None,
                        course_email=course[0]["email"],
                        course_number=course[0]["phoneNumber"],
                        address=course[0]["address"],
                        remote_link=course[0]["remoteLink"]
                    ),
                    "attachments": []
                }
                tries = 0
                while True:
                    try:
                        email = send_email(
                            receiver=[user.email],
                            email_content=template
                        )
                        if email:
                            break
                    except Exception:
                        log.error(f"Attempting to resend email to {email}")
                        if tries >= 5:
                            log.exception(
                                f"Failed to send email to user email {user.email}")
                    tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on registration {user}")
    return False

# TODO: test notification


async def student_bundle_enroll_notification(users: list, bundle_id: str):
    try:
        template = load_template(
            "/source/src/content/templates/bundle_enroll/student_enroll_bundle.json")
        if not template:
            raise Exception("Failed to load template")

        bundle = await get_bundle(bundle_id)
        if not bundle[0]:
            raise Exception("Failed to get bundle")

        text_users = []
        email_users = []
        for user in users:
            if user.textNotifications:
                text_users.append(user)
            if user.emailNotifications:
                email_users.append(user)
        if text_users:
            for user in text_users:
                continue
            # TODO: send text confirmation
            pass
        if email_users:
            for user in email_users:
                template = {
                    "subject": template["email"]["subject"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName
                    ),
                    "body": template["email"]["body"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName,
                        company_phone=os.getenv("COMPANY_PHONE", "1234"),
                        company_url=os.getenv(
                            "COMPANY_URL", 'doitsolutions.io'),
                        company_email=os.getenv(
                            "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                        bundle_name=bundle[0]["bundleName"]
                    ),
                    "attachments": []
                }
                tries = 0
                while True:
                    try:
                        email = send_email(
                            receiver=[user.email],
                            email_content=template
                        )
                        if email:
                            break
                    except Exception:
                        log.error(f"Attempting to resend email to {email}")
                        if tries >= 5:
                            log.exception(
                                f"Failed to send email to user email {user.email}")
                    tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on registration {user}")
    return False

# TODO: test notification


async def self_bundle_enroll_notification(users: list, bundle_id: str):
    try:
        template = load_template(
            "/source/src/content/templates/bundle_enroll/self_enroll_bundle.json")
        if not template:
            raise Exception("Failed to load template")

        bundle = await get_bundle(bundle_id)
        if not bundle[0]:
            raise Exception("Failed to get bundle")

        text_users = []
        email_users = []
        for user in users:
            if user.textNotifications:
                text_users.append(user)
            if user.emailNotifications:
                email_users.append(user)
        if text_users:
            for user in text_users:
                continue
            # TODO: send text confirmation
            pass
        if email_users:
            for user in email_users:
                template = {
                    "subject": template["email"]["subject"],
                    "body": template["email"]["body"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName,
                        company_phone=os.getenv("COMPANY_PHONE", "1234"),
                        company_url=os.getenv(
                            "COMPANY_URL", 'doitsolutions.io'),
                        company_email=os.getenv(
                            "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                        bundle_name=bundle[0]["bundleName"],
                    ),
                    "attachments": []
                }
                tries = 0
                while True:
                    try:
                        email = send_email(
                            receiver=[user.email],
                            email_content=template
                        )
                        if email:
                            break
                    except Exception:
                        log.error(f"Attempting to resend email to {email}")
                        if tries >= 5:
                            log.exception(
                                f"Failed to send email to user email {user.email}")
                    tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on registration {user}")
    return False


async def self_enroll_notification(user: User, course_id: str, registration_status: str):
    try:
        template = load_template(
            "/source/src/content/templates/course_enroll/self_enroll.json")
        course = await get_course(course_id)
        if not course[0]:
            raise Exception("Failed to get course")
        if not template:
            raise Exception("Failed to load template")
        instructors = []
        if course[0]['instructors']:
            for instructor in course[0]['instructors']:
                instructors.append(
                    f"{instructor['firstName']} {instructor['lastName']}")
        if user.textNotifications:
            # TODO: send text confirmation
            pass
        if user.emailNotifications:
            template = {
                "subject": template["email"]["subject"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName
                ),
                "body": template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_url=os.getenv("COMPANY_URL", 'doitsolutions.io'),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io"),
                    course_name=course[0]["courseName"],
                    first_class_dtm=course[0]["startDate"],
                    instructors=', '.join(
                        instructors) if instructors else None,
                    course_email=course[0]["email"],
                    course_number=course[0]["phoneNumber"],
                    address=course[0]["address"],
                    remote_link=course[0]["remoteLink"],
                    registration_status=registration_status
                )
            }
            tries = 0
            while True:
                try:
                    email = send_email(
                        receiver=[user.email],
                        email_content=template
                    )
                    if email:
                        break
                except Exception:
                    log.error(f"Attempting to resend email to {email}")
                    if tries >= 5:
                        log.exception(
                            f"Failed to send email to user email {user.email}")
                tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on registration {user}")
    return False


# TODO: test notification
def scheduled_class_update_notifcation(users: list, new_class: dict, original_class: dict, course: dict):
    if new_class["is_complete"]:
        return True

    try:
        template = load_template(
            "/source/src/content/templates/course_update/scheduled_class_update.json")
        if not template:
            raise Exception("Failed to load template")
        text_users = []
        email_users = []
        for user in users:
            if user["text_allowed"]:
                text_users.append(user)
            if user["email_allowed"]:
                email_users.append(user)
        if text_users:
            for user in text_users:
                continue
            # TODO: send text confirmation
            pass
        if email_users:
            for user in email_users:
                template = {
                    "subject": template["email"]["subject"].format(
                        course_name=course["courseName"]
                    ),
                    "body": template["email"]["body"].format(
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        name=user.firstName,
                        original_start_time=original_class["start_dtm"],
                        course_name=course["courseName"],
                        new_start_date=new_class["start_dtm"],
                        company_phone=os.getenv("COMPANY_PHONE", "1234"),
                        company_email=os.getenv(
                            "COMPANY_EMAIL", "rmiller.doitsolutions.io")
                    ),
                    "attachments": [
                        class_calendar_invite(
                            class_time=original_class, cancel=True, course=course, user=user),
                        class_calendar_invite(
                            class_time=new_class, cancel=False, course=course)
                    ]

                }
                tries = 0
                while True:
                    try:
                        email = send_email(
                            receiver=[user["email"]],
                            email_content=template
                        )
                        if email:
                            break
                    except Exception:
                        log.error(f"Attempting to resend email to {email}")
                        if tries >= 5:
                            log.exception(
                                f"Failed to send email to user email {user.email}")
                    tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on registration {user}")
    return False

# TODO: test notification


def canceled_course_notification(course: dict, students: list, instructors: list, first_class_dtm: datetime.datetime):
    users = []
    if students:
        users.extend(students)
    if instructors:
        users.extend(instructors)

    try:
        template = load_template(
            "/source/src/content/templates/course_update/canceled_course.json")
        if not template:
            raise Exception("Failed to load template")
        tz_out = pytz.timezone('America/New_York')
        first_class_dtm = first_class_dtm.astimezone(tz_out)
        text_users = []
        email_users = []
        if users:
            for user in users:
                if user["text_allowed"]:
                    text_users.append(user)
                if user["email_allowed"]:
                    email_users.append(user)
        if text_users:
            for user in text_users:
                continue
            # TODO: send text confirmation
            pass
        if email_users:
            for user in email_users:
                template = {
                    "subject": template["email"]["subject"].format(
                        course_name=course["courseName"]
                    ),
                    "body": template["email"]["body"].format(
                        name=user["first_name"],
                        company_name=os.getenv(
                            "COMPANY_NAME", "ABC Safety Group"),
                        course_name=course["courseName"],
                        first_class_dtm=datetime.datetime.strftime(
                            first_class_dtm, "%m/%d/%Y %-I:%M %p"),
                        company_phone=os.getenv("COMPANY_PHONE", "1234"),
                        company_email=os.getenv(
                            "COMPANY_EMAIL", "rmiller.doitsolutions.io")
                    ),
                    # "attachments": [
                    #     class_calendar_invite(class_time=original_class, cancel=True, course=course, user=user),
                    #     class_calendar_invite(class_time=new_class, cancel=False, course=course)
                    # ]

                }
                tries = 0
                while True:
                    try:
                        email = send_email(
                            receiver=[user["email"]],
                            email_content=template
                        )
                        if email:
                            break
                    except Exception:
                        log.error(f"Attempting to resend email to {email}")
                        if tries >= 5:
                            log.exception(
                                f"Failed to send email to user email {user.email}")
                    tries += 1
        return True
    except Exception:
        log.exception(f"Failed to notify user on cancelled course {user}")
    return False

# TODO: test notification


def enrollment_update_notification(user: User, course: dict, bundle: dict, new_status: str) -> bool:
    try:
        template = load_template(
            "/source/src/content/templates/register/enroll_update.json")
        if not template:
            raise Exception("Failed to load template")
        if user.textNotifications:
            # TODO: send text confirmation
            pass
        if user.emailNotifications:
            if course:
                body = template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    course_name=course["courseName"],
                    new_status=new_status,
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io")
                )
            if bundle:
                body = template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    course_name=bundle["bundleName"],
                    new_status=new_status,
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io")
                )
            template = {
                "subject": template["email"]["subject"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName
                ),
                "body": body
            }

            tries = 0
            while True:
                try:
                    email = send_email(
                        receiver=[user.email],
                        email_content=template
                    )
                    if email:
                        break
                except Exception:
                    log.error(f"Attempting to resend email to {email}")
                    if tries >= 5:
                        log.exception(
                            f"Failed to send email to user email {user.email}")
                tries += 1
        return True
    except Exception:
        log.exception(
            f"Failed to notify enrollment status update for user {user}")
    return False

# TODO: test notification


def remove_enrollment_update_notification(user: User, course: dict = None, bundle: dict = None) -> bool:
    try:
        template = load_template(
            "/source/src/content/templates/register/unenroll_update.json")
        if not template:
            raise Exception("Failed to load template")
        if user.textNotifications:
            # TODO: send text confirmation
            pass
        if user.emailNotifications:
            if course:
                body = template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    course_name=course["courseName"],
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io")
                )
            if bundle:
                body = template["email"]["body"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName,
                    course_name=bundle["bundleName"],
                    company_phone=os.getenv("COMPANY_PHONE", "1234"),
                    company_email=os.getenv(
                        "COMPANY_EMAIL", "rmiller.doitsolutions.io")
                )
            template = {
                "subject": template["email"]["subject"].format(
                    company_name=os.getenv("COMPANY_NAME", "ABC Safety Group"),
                    name=user.firstName
                ),
                "body": body
            }

            tries = 0
            while True:
                try:
                    email = send_email(
                        receiver=[user.email],
                        email_content=template
                    )
                    if email:
                        break
                except Exception:
                    log.error(f"Attempting to resend email to {email}")
                    if tries >= 5:
                        log.exception(
                            f"Failed to send email to user email {user.email}")
                tries += 1
        return True
    except Exception:
        log.exception(
            f"Failed to notify enrollment status update for user {user}")
    return False

# TODO: test notification


def training_connect_failure_notification(body: str, stack_trace: str):
    try:
        template = load_template(
            "/source/src/content/templates/training_connect/training_connect_error.json")
        if not template:
            raise Exception("Failed to load template")

        body = template["email"]["body"].format(
            error_message=body,
            stack_trace=stack_trace
        )

        template = {
            "subject": template["email"]["subject"],
            "body": body
        }

        tries = 0
        while True:
            try:
                email = send_email(
                    receiver=['rmiller@doitsolutions.io',
                              'aosmolovsky@doitsolutions.io'],
                    email_content=template
                )
                if email:
                    break
            except Exception:
                log.error(f"Attempting to resend email to {email}")
                if tries >= 5:
                    log.exception(
                        "Failed to send email for training connect error")
            tries += 1
        return True
    except Exception:
        log.exception("Failed to send email for training connect error")
    return False

# TODO: notifications
#   - Certificate generated
#   - Quiz Link
#   - Survey Link
