import os
from datetime import datetime, timedelta
import time
import pytz
import asyncio

from src import log
from src.database.sql import get_connection, acquire_connection
from src.utils.mailer import send_email, class_calendar_invite
from src.modules.notifications import load_template
from src.database.sql.user_functions import get_instructors, get_students
from src.database.sql.course_functions import get_course


async def complete_previous_classes():
    query = """
        UPDATE
            course_dates
        SET
            is_complete=$1
        WHERE
            end_dtm < $2;
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(query, True, datetime.utcnow() - timedelta(days=3))
        return True
    except Exception:
        log.exception("Failed to mark scheduled classes as complete")
    return False


async def get_scheduled_courses(cur_time: datetime, week_later: datetime):
    """function to get scheduled courses

    Args:
        cur_time (datetime): date time right now
        week_later (datetime): date time a week from now

    Returns:
        tuple: returns course dates in between cur_time and week_later
    """

    scheduleQuery = """
        SELECT
            cd.course_id,
            cd.start_dtm,
            cd.end_dtm,
            cd.series_number
        FROM courses c
        JOIN course_dates cd
        ON c.course_id = cd.course_id
        WHERE cd.start_dtm > $1 AND cd.start_dtm < $2 AND c.is_complete != TRUE
        ORDER BY cd.start_dtm ASC;
    """

    schedule = None
    db_pool = await get_connection()
    async with acquire_connection(db_pool) as conn:
        try:
            schedule = await conn.fetch(scheduleQuery, cur_time, week_later)
        except Exception:
            log.exception("Failed to get course dates")

    return schedule


async def build_recipients(course_id: str) -> list:
    """function to return recipients for a course

    Args:
        course_id (str): course id used to get students and instructors

    Returns:
        list: list of instructors and students for a course
    """

    recipients = []
    students = await get_students(course_id=course_id)
    if students:
        recipients.extend(students)

    instructors = await get_instructors(course_id=course_id)
    if instructors:
        recipients.extend(instructors)

    return recipients


def build_notification(
    course_name: str,
    start_time: datetime,
    end_time: datetime,
    days: str,
    attachments: list = None,
    address: str = None,
    remote_link: str = None,
    name: str = None
):
    # datetime.strftime(row[2], "%m/%d/%Y %-I:%M %p"),
    tz_out = pytz.timezone('America/New_York')
    start_time = start_time.astimezone(tz_out).strftime("%m/%d/%Y %-I:%M %p")
    end_time = end_time.astimezone(tz_out).strftime("%m/%d/%Y %-I:%M %p")
    template = load_template(
        "/source/src/content/templates/course_reminders/schedule_reminder.json")

    location = ""
    if remote_link:
        location += f'<p>Remote Link: {remote_link}</p>'
    if address:
        location += f'<p>Address: {address}</p>'

    return {
        "email": {
            "subject": template["email"]["subject"].format(
                course_name=course_name
            ),
            "body": template["email"]["body"].format(
                name=name,
                company_name=os.getenv("COMPANY_NAME", None),
                course_name=course_name,
                start_time=start_time,
                time_till_class=days,
                company_phone=os.getenv("COMPANY_PHONE", None),
                location=location,
                company_email=os.getenv("COMPANY_EMAIL", None),
            ),
            "attachments": attachments
        },
        "text": template["text"].format(
            name=name,
            company_name=os.getenv("COMPANY_NAME", None),
            course_name=course_name,
            start_time=start_time,
            time_till_class=days,
            company_phone=os.getenv("COMPANY_PHONE", None),
            remote_link=remote_link,
            address=address
        ),
    }


def send_notifications(
    sender: str = "rmiller@doitsolutions.io",
    recipients: list = None,
    course_name: str = None,
    start_time: datetime = None,
    end_time: datetime = None,
    days: str = None,
    attachment: str = None,
    course: dict = None

):
    """function to send notifications

    Args:
        sender (str, optional): email of person sending the email. Defaults to "rmiller@doitsolutions.io".
        recipients (list, optional): list of emails that the email needs to be sent to. Defaults to None.
        content (dict, optional): content of the email, attachments, message, etc. Defaults to None.
    """
    if not recipients:
        return

    for recipient in recipients:
        content = build_notification(
            course_name=course_name,
            start_time=start_time,
            end_time=end_time,
            days=days,
            attachments=[attachment] if attachment else None,
            address=course["address"] if course["address"] else None,
            remote_link=course["remoteLink"] if course["remoteLink"] else None,
            name=recipient["first_name"]
        )
        if recipient["email_allowed"]:
            while True:
                sent = send_email(
                    sender=sender,
                    receiver=[recipient["email"]],
                    email_content=content["email"],
                )
                if sent:
                    break

        if recipient["text_allowed"]:
            print("send text notification")

        time.sleep(5)


async def monitor_courses():
    """
    Function to monitor the courses and send notifications based on time
    """

    log.info("Checking for course dates")

    cur_time = datetime.utcnow()
    week_later = cur_time + timedelta(days=8)

    await complete_previous_classes()
    schedule = await get_scheduled_courses(cur_time=cur_time, week_later=week_later)

    if schedule:
        for row in schedule:
            course_id = row['course_id']
            start_dtm = row['start_dtm']
            end_dtm = row['end_dtm']
            series_number = row['series_number']

            time_difference = start_dtm - datetime.utcnow()

            if time_difference.days == 10:
                course = await get_course(course_id=course_id)
                course = course[0]

                recipients = await build_recipients(course_id=course_id)
                calendar_meeting = class_calendar_invite(
                    class_time={
                        "start_dtm": start_dtm,
                        "end_dtm": end_dtm,
                        "series_number": series_number
                    },
                    course=course
                )

                send_notifications(
                    recipients=recipients,
                    course_name=course["courseName"],
                    start_time=start_dtm,
                    end_time=end_dtm,
                    days=", in 10 days",
                    attachment=calendar_meeting,
                    course=course
                )
                continue

            if time_difference == 7:
                course = await get_course(course_id=course_id)
                course = course[0]

                recipients = await build_recipients(course_id=course_id)
                send_notifications(
                    recipients=recipients,
                    course_name=course["courseName"],
                    start_time=start_dtm,
                    end_time=end_dtm,
                    days=", in 7 days",
                    course=course
                )
                continue

            if time_difference == 3:
                course = await get_course(course_id=course_id)
                course = course[0]
                recipients = await build_recipients(course_id=course_id)

                calendar_meeting = class_calendar_invite(
                    class_time={
                        "start_dtm": start_dtm,
                        "end_dtm": end_dtm,
                        "series_number": series_number
                    },
                    course=course
                )
                send_notifications(
                    recipients=recipients,
                    course_name=course["courseName"],
                    start_time=start_dtm,
                    end_time=end_dtm,
                    days=", in 3 days",
                    course=course
                )

                continue

            if time_difference.days == 1:
                course = await get_course(course_id=course_id)
                course = course[0]

                calendar_meeting = class_calendar_invite(
                    class_time={
                        "start_dtm": start_dtm,
                        "end_dtm": end_dtm,
                        "series_number": series_number
                    },
                    course=course
                )
                recipients = await build_recipients(course_id=course_id)
                send_notifications(
                    recipients=recipients,
                    course_name=course["courseName"],
                    start_time=start_dtm,
                    end_time=end_dtm,
                    days=", in 1 day",
                    course=course,
                    attachment=calendar_meeting
                )

                continue

            if 1 < time_difference.total_seconds() / 3600 <= 24:
                course = await get_course(course_id=course_id)
                course = course[0]

                recipients = await build_recipients(course_id=course_id)
                if start_dtm.date() == datetime.utcnow().date():
                    day = ', today'
                else:
                    day = ', tomorrow'
                send_notifications(
                    recipients=recipients,
                    course_name=course["courseName"],
                    start_time=start_dtm,
                    end_time=end_dtm,
                    days=day,
                    course=course
                )

                continue


if __name__ == "__main__":
    asyncio.run(
        monitor_courses()
    )
