import re
import base64
from pyppeteer import launch
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import json

from src import log
from src.database.sql import get_connection, acquire_connection
from src.utils.generate_random_code import generate_random_code
from src.database.sql.user_functions import get_user
from src.api.api_models import global_models


def read_and_encode_image(file_path):
    with open(file_path, 'rb') as image_file:
        image_data = image_file.read()

    base64_image = base64.b64encode(image_data).decode()
    return base64_image


async def html_to_png(html_content, output_path):
    try:
        browser = await launch(
            executablePath='/usr/bin/google-chrome-stable',
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-software-rasterizer',
                '--single-process',
                '--disable-dev-shm-usage',
                '--no-zygote'
            ]
        )
        page = await browser.newPage()
        await page.setViewport({'width': 1300, 'height': 1000})
        pattern = r'src="([a-z0-9/._]+)"'

        def replace_src(match):
            src = match.group(1)
            src_path = f'./src/content/certificates{src[1:]}'

            base64_image = read_and_encode_image(src_path)

            return f'src="data:image/jpeg;base64,{base64_image}"'

        modified_html = re.sub(pattern, replace_src, html_content)

        await page.setContent(modified_html)
        await page.addStyleTag(path="./src/content/certificates/styles/output.css")
        await page.waitFor(500)
        screenshot = await page.screenshot()
        await browser.close()

        return screenshot

    except Exception as e:
        raise e


async def generate_certificate_func(
    student_full_name: str,
    instructor_full_name: str,
    certificate_name: str,
    completion_date: datetime,
    expiration_date: datetime,
    certificate_number: str,
    email: str = None,
    phone_number: str = None,
    template: str = None,
    save: bool = True
):
    try:
        if not template:
            template = './src/content/certificates/index.html'

        with open(template, 'r') as file:
            generation_template = file.read()
            file.close()

        formatted_completion_date = completion_date.strftime("%Y-%m-%d")

        html_content = generation_template.replace(
            "{student_full_name}", student_full_name)
        html_content = html_content.replace(
            "{instructor_full_name}", instructor_full_name)
        html_content = html_content.replace(
            "{certificate_name}", certificate_name)
        html_content = html_content.replace(
            "{completion_date}", formatted_completion_date)
        html_content = html_content.replace(
            "{certificate_number}", certificate_number)

        output_path = f"./src/content/user_certificates/{student_full_name.replace(' ', '_')}_{certificate_name}.png"

        try:
            output = await html_to_png(html_content, output_path)
        except Exception as e:
            raise e

        if save:
            if not email and not phone_number:
                return (output, "Unable to find user in Learning Management System without an email or phone number provided.")
            saved = await save_user_certificate(
                certificate_number=certificate_number,
                completion_date=completion_date,
                expiration_date=expiration_date,
                email=email,
                phone_number=phone_number,
                certificate_name=certificate_name
            )
            if not saved:
                return (
                    output,
                    f"Unable to find user in Learning Management System with email: {email} or phone number: {phone_number} for certificate relation."
                )

        return output
    except Exception as e:
        raise e


async def generate_certificate(user: global_models.User, course: dict, certificate: dict = None):

    certificate_number = generate_random_code(15)

    completion_date = datetime.utcnow()
    expiration_date = None
    certificate_name = ""
    certificate_name += course['courseName']
    if course.get('courseCode'):
        certificate_name += f", {course['courseCode']}"

    formatted_values = {
        "student_full_name": f"{user.firstName} {user.lastName}",
        "instructor_full_name": (f"{course['instructors'][0]['firstName']} {course['instructors'][0]['lastName']}"
                                 if course['instructors'] else os.getenv('COMPANY_NAME')),
        "instructor_id": course['instructors'][0]['userId'] if course['instructors'] else 'd8adb06f-1db0-43be-8823-bd26460408fb',
        "certificate_name": certificate_name,
        "completion_date": completion_date,
    }

    certificate_id = None
    if certificate:
        if certificate['certificateId']:
            certificate_id = certificate['certificateId']
        if certificate['certificateName']:
            certificate_name = certificate['certificateName']

        if certificate['certificateLength']:
            certificate_length = json.loads(certificate['certificateLength'])
            if certificate_length["years"]:
                expiration_date = completion_date + relativedelta(years=certificate_length["years"])
            if certificate_length["months"]:
                if expiration_date:
                    expiration_date = expiration_date + relativedelta(months=certificate_length["months"])
                else:
                    expiration_date = completion_date + relativedelta(months=certificate_length["months"])

        formatted_values.update({
            "instructor_full_name": (f"{course['instructors'][0]['firstName']} {course['instructors'][0]['lastName']}"
                                     if course['instructors'] else os.getenv("COMPANY_NAME")),
            "certificate_name": certificate_name,
            "expiration_date": expiration_date
        })

    try:
        certificate = await generate_certificate_func(
            student_full_name=formatted_values.get('student_full_name'),
            instructor_full_name=formatted_values.get('instructor_full_name'),
            certificate_name=formatted_values.get('certificate_name'),
            completion_date=formatted_values.get('completion_date'),
            certificate_number=certificate_number,
            expiration_date=formatted_values.get('expiration_date'),
            save=False
        )
        if not certificate:
            return False

    except Exception:
        log.exception("An exception occured while generating the certificate")
        return False

    # save certificate to user
    saved = await save_user_certificate(
        certificate_number=certificate_number,
        instructor_id=formatted_values['instructor_id'],
        completion_date=completion_date,
        course_id=course["courseId"],
        user=user,
        certificate_id=certificate_id,
        expiration_date=expiration_date
    )

    if not saved:
        return False

    # TODO: NOTIFY USER OF CERTIFICATE GENERATION
    # DO WE WANT TO EMAIL THEM THE CERTIFICATE OR HAVE THEM LOGIN TO DOWNLOAD IT?

    return True


async def save_user_certificate(
    certificate_number: str,
    completion_date: datetime,
    instructor_id: str = None,
    expiration_date: datetime = None,
    course_id: str = None,
    email: str = None,
    phone_number: str = None,
    user: global_models.User = None,
    certificate_id: str = None,
    certificate_name: str = None,

):
    # do sql query for import into certificate table here
    if email and not user:
        user = await get_user(email=email)
    if phone_number and not user:
        user = await get_user(phoneNumber=phone_number)

    if not user:
        return False

    query = """
        INSERT INTO user_certificates (
            user_id,
            certificate_id,
            course_id,
            completion_date,
            expiration_date,
            instructor_id,
            certificate_number,
            certificate_name
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8
        );
    """
    try:
        db_pool = await get_connection()
        async with acquire_connection(db_pool) as conn:
            await conn.execute(
                query,
                user.userId,
                certificate_id,
                course_id,
                completion_date,
                expiration_date,
                instructor_id,
                certificate_number,
                certificate_name
            )
        return True

    except Exception:
        log.exception(
            f"An error occurred while creating a certificate for {user.userId if user else email}")

    return False
