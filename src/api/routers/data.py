from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
import pandas as pd
from passlib.hash import pbkdf2_sha256
import numpy as np
import uuid
import json
from io import BytesIO
from datetime import datetime
import os
from zipfile import ZipFile
from typing import List, Tuple

from src import redis_client
from src import log
from src.api.lib.auth.auth import AuthClient
from src.api.api_models import global_models
from src.utils.roles import roles
from src.utils.snake_case import camel_to_snake
from src.api.api_models.data import export_users, import_courses, import_students
from src.api.api_models.courses.create import General
from src.api.api_models.courses import bundle
from src.database.sql.user_functions import get_users_for_export, create_user, manage_user_roles, get_user, get_user_type
from src.database.sql.audit_log_functions import submit_audit_record
from src.database.sql.course_functions import create_course, create_bundle
from src.api.lib.base_responses import server_error, user_error, successful_response
from src.utils.generate_random_code import generate_random_code
from src.utils.certificate_generation import generate_certificate_func
from src.api.api_models.users import lookup

router = APIRouter(
    prefix="/data",
    tags=["Data"],
    responses={404: {"description": "Details not found"}}
)


@router.post(
    "/export/{roleName}",
    description="Route to export data by role",
    response_model=export_users.Output
)
async def export_role_route(roleName: str, content: export_users.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        if roleName not in roles:
            return user_error(message="This role does not exist")

        users = await get_users_for_export(userIds=content.userIds, role=roleName)
        df = pd.DataFrame.from_dict(users)
        filePath = f'./src/content/exports/{uuid.uuid4()}.csv'
        df.to_csv(filePath, index=False, header=True)

        await submit_audit_record(
            route=f"data/export/{roleName}",
            details=f"user {user.firstName} {user.lastName} exported {roleName} {', '.join(content.userIds)}",
            user_id=user.userId
        )
        return FileResponse(filePath)
    except Exception:
        log.exception(f"Failed to generate {roleName} export")
        return server_error(message=f"Failed to generate {roleName} export")


# Function to serialize datetime objects to strings
def datetime_serializer(o):
    if isinstance(o, datetime):
        return o.__str__()


@router.post(
    "/import/certificates",
    description="Route to import excel file certs to system",
)
async def import_certificates(file: UploadFile = File(None), user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not file:
        return user_error(message="File must be provided")

    required_columns = [
        "course_name",
        "issue_date",
        "expiry_date",
        "instructor",
        "first_name",
        "last_name"
    ]

    try:
        content = await file.read()
        df = pd.read_excel(BytesIO(content))
        df = df.replace(r'^\s*$', np.nan, regex=True)
        df = df.replace({np.nan: None})

        # Check for missing columns
        missing_columns = [
            col for col in required_columns if col not in df.columns]
        if missing_columns:
            return user_error(
                message=f"Missing columns: {', '.join(missing_columns)}"
            )

        json_data = df.to_dict(orient='records')
        if not json_data:
            return user_error(
                message="Sheet is formatted incorrectly please fix and reupload."
            )

        json_data = [d for d in json_data if not all(
            v == '' or not v or v == ' ' for v in d.values())]

        missing_values = []
        for idx, row in enumerate(json_data):
            for col in required_columns:
                if not row.get(col):
                    missing_values.append(f"\nrow: {idx+1} col: {col}")
        # Check for missing values
        if missing_values:
            return user_error(
                message=f"Missing values in required columns: {', '.join(missing_values)}"
            )

        # Prepare data for upload
        max_length = len(json_data)
        for idx, u in enumerate(json_data):
            u['upload_info'] = {
                "uploader": user.email,
                "position": idx + 1,
                "max": max_length,
                "file_name": file.filename,
                "upload_type": "certificate"
            }

        if os.getenv("ENVIRONMENT", "prod").lower() == "prod":
            json_data = json.dumps(json_data, default=datetime_serializer)

            published = redis_client.publish(
                os.getenv("TRAINING_CONNECT_QUEUE", 'training_connect_queue'),
                json_data
            )
            if not published:
                raise Exception("Failed to post data to redis")

        await submit_audit_record(
            route="data/import/certificates",
            details=f"user {user.firstName} {user.lastName} started import certificates for {file.filename}",
            user_id=user.userId
        )
        return successful_response(
            message="Import started."
        )

    except Exception:
        log.exception("An error occured while uploading sheet")
        return server_error(
            message="Unable to import sheet"
        )


@router.post(
    "/download/certificates",
    description="Route to import excel file certs to get an output of certificates",
)
async def download_certificates(file: UploadFile = File(None), user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not file:
        return user_error(message="File must be provided")

    required_columns = [
        "course_name",
        "issue_date",
        "expiry_date",
        "instructor",
        "first_name",
        "last_name"
    ]

    content = await file.read()
    df = pd.read_excel(BytesIO(content))
    df = df.replace(r'^\s*$', np.nan, regex=True)
    df = df.replace({np.nan: None})

    # Check for missing columns
    missing_columns = [
        col for col in required_columns if col not in df.columns]
    if missing_columns:
        return user_error(
            message=f"Missing columns: {', '.join(missing_columns)}"
        )

    json_data = df.to_dict(orient='records')
    if not json_data:
        return user_error(
            message="Sheet is formatted incorrectly please fix and reupload."
        )

    json_data = [d for d in json_data if not all(
        v == '' or not v or v == ' ' for v in d.values())]

    missing_values = []
    for idx, row in enumerate(json_data):
        for col in required_columns:
            if not row.get(col):
                missing_values.append(f"\nrow: {idx+1} col: {col}")
    # Check for missing values
    if missing_values:
        return user_error(
            message=f"Missing values in required columns: {', '.join(missing_values)}"
        )

    certs = []
    try:
        for _, uploaded in enumerate(json_data):
            cert = await generate_certificate_func(
                student_full_name=f"{uploaded['first_name']} {uploaded['last_name']}",
                instructor_full_name=uploaded["instructor"],
                certificate_name=uploaded["course_name"],
                completion_date=uploaded["issue_date"],
                expiration_date=uploaded["expiry_date"],
                certificate_number=uploaded["certificate_id"],
                save=False
            )
            if isinstance(cert, tuple):
                certs.append(
                    {"cert": cert[0], "name": f"{uploaded['first_name']} {uploaded['last_name']}"})
            else:
                certs.append(
                    {"cert": cert, "name": f"{uploaded['first_name']} {uploaded['last_name']}"})

        zip_buffer = BytesIO()

        with ZipFile(zip_buffer, 'w') as zipf:
            for i, file in enumerate(certs):
                full_name = file["name"]
                random = generate_random_code(4)
                zipf.writestr(f'{full_name}_{random}.png', file['cert'])

        await submit_audit_record(
            route="data/import/certificates",
            details=f"user  {user.firstName} {user.lastName} downloaded certificates for {file.filename}",
            user_id=user.userId
        )
        zip_buffer.seek(0)
        return StreamingResponse(zip_buffer, media_type="application/x-zip-compressed")

    except Exception:
        log.exception("Something went wrong while creating certificates.")

    return server_error(message="Failed to generate certificates")


@router.get(
    "/import/certificates/template",
    description="Route to get excel file template to upload certificte history",
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def download_certificates_template():
    try:
        return FileResponse("./src/content/imports/certificate_template.xlsx")
    except Exception:
        log.exception(
            "Something went wrong when trying to retrive the certificates template")
        return server_error(message="Something went wrong when retrieving the certificates template.")


@router.get(
    "/import/courses/template",
    description="Route to get excel file template to upload courses/course history",
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def download_courses_template():
    try:
        return FileResponse("./src/content/imports/course_template.xlsx")
    except Exception:
        log.exception(
            "Something went wrong when trying to retrive the courses template")
        return server_error(message="Something went wrong when retrieving the courses template.")


@router.post(
    "/import/courses/upload",
    description="Route to import excel file courses to system",
    response_model_exclude_unset=True
)
async def import_courses_upload_route(file: UploadFile = File(None)):
    if not file:
        return user_error(message="File must be provided")

    required_columns = [
        "Today's Date",
        "ID #",
        "Course Name",
        "Language",
        "Start Date",
        "Start Time",
        "End Time",
        "Online Class Link",
        "Password",
        "Street",
        "Rm/Fl",
        "City",
        "State",
        "ZIP",
        "Instructor Name",
        "Price",
        "Private?",
        "Code"
    ]

    unnecessary_columns = [
        "Today's Date",
        "ID #",
        "Private?",
        "Online Class Link",
        "Password",
        "Street",
        "Rm/Fl",
        "City",
        "State",
        "ZIP",
        "Instructor Name"
    ]

    try:
        content = await file.read()
        df = pd.read_excel(BytesIO(content))
        df = df.replace(r'^\s*$', np.nan, regex=True)
        df = df.replace({np.nan: None})

        # Check for missing columns
        missing_columns = [
            col for col in required_columns if col not in df.columns]
        if missing_columns:
            return user_error(
                message=f"Missing columns: {', '.join(missing_columns)}"
            )

        json_data = df.to_dict(orient='records')
        if not json_data:
            return user_error(
                message="Sheet is formatted incorrectly please fix and reupload."
            )

        address_fields = ["Street", "Rm/Fl", "City", "State", "ZIP"]
        error_messages = {
            col: f"No {col} provided and is required" for col in required_columns}

        formatted_json_data = []
        for row in json_data:
            for col in required_columns:
                col = col.strip()
                if col in address_fields and not row["Online Class Link"] and not row[col] and row[col] is None:
                    row.update(
                        {"failed": True, "reason": f"No {col} while address is provided"})
                    continue

                if col not in unnecessary_columns and not row.get(col) and not col == "Price":
                    row.update({"failed": True, "reason": error_messages[col]})
                    continue

                if col == "Price" and not row.get(col):
                    row[col] = 0

                if col == "Start Date":
                    try:
                        row["Start Date"] = datetime.strftime(
                            row["Start Date"], "%m/%d/%Y")
                    except Exception:
                        log.exception("failed to convert Start Date")
                        row.update(row.update(
                            {"failed": True, "reason": "Invalid Start Date format"}))

                if col == "Start Time":
                    try:
                        row["Start Time"] = row["Start Time"].strftime(
                            "%-I:%M %p")
                    except Exception:
                        log.exception("failed to convert Start Time")
                        row.update(row.update(
                            {"failed": True, "reason": "Invalid Start Time format"}))

                if col == "End Time":
                    try:
                        row["End Time"] = row["End Time"].strftime("%-I:%M %p")
                    except Exception:
                        log.exception("failed to convert End Time")
                        row.update(row.update(
                            {"failed": True, "reason": "Invalid End Time format"}))

            if not row.get("failed"):
                row.update({"failed": False})

            row["Today's Date"] = str(
                row["Today's Date"]) if row["Today's Date"] else None

            first_row = {"failed": row.get(
                "failed", False), "reason": row.get("reason")}
            second_row = {k: v for k, v in row.items() if k not in [
                "reason", "failed"]}
            formatted_json_data.append({**first_row, **second_row})

        return successful_response(
            payload={
                "courses": formatted_json_data
            }
        )
    except Exception:
        log.exception("An error ocurred while parsing courses")
        return server_error(message="Failed to parse courses")


async def __create_courses(courses: List[import_courses.Course], user: global_models.User, series: bool = False) -> Tuple[list, list]:
    failed_courses = []
    course_ids = []
    for course in courses:
        if not course.language:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have a language provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have a language provided"
                })
            continue

        if not course.schedule:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have a schedule provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have a schedule provided"
                })
            continue

        address = ""
        if course.street:
            address += str(course.street)
        if course.rmFl:
            address += f" {str(course.rmFl)}"

        if not address and not course.onlineClassLink:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have an address or onlineClassLink provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have an address or onlineClassLink provided"
                })
            continue

        if not course.onlineClassLink and not address and not course.street:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have a street provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have a street provided"
                })
            continue

        if not course.onlineClassLink and not address and not course.city:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have a city provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have a city provided"
                })
            continue

        if not course.onlineClassLink and not address and not course.state:
            failed_courses.append({
                "courseName": course.courseName,
                "reason": "Course does not have a state provided"
            })
            continue

        if not course.onlineClassLink and not address and not course.zip:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have a zip provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have a zip provided"
                })
            continue

        instructors = []
        if course.instructorNames:

            for instructor in course.instructorNames:
                instructor_name = instructor.split(" ")
                to_lookup = lookup.Input(
                    firstName=instructor_name[0],
                    lastName=instructor_name[1]
                )
                found_instructors, _ = await get_user_type(user=to_lookup, roleName="instructor")
                if found_instructors:
                    instructors.append(found_instructors[0]["userId"])
        if not instructors:
            instructors.append("d8adb06f-1db0-43be-8823-bd26460408fb")

        if not course.price and not isinstance(course.price, (int, float)):
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have a price provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have a price provided"
                })
            continue

        course.price = round(course.price, 2)

        if not course.code:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Series does not have a code provided"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Course does not have a code provided"
                })
            continue

        course_id = str(uuid.uuid4())

        instruction_types = []
        if course.onlineClassLink:
            instruction_types.append("Remote")

        if address:
            instruction_types.append("In-Person")

        formatted_classes = []
        try:
            for course_time in course.schedule:
                start_time = datetime.strptime(
                    f"{course_time.date} {course_time.startTime}", "%m/%d/%Y %I:%M %p")
                end_time = datetime.strptime(
                    f"{course_time.date} {course_time.endTime}", "%m/%d/%Y %I:%M %p")
                formatted_classes.append((start_time, end_time))
        except Exception:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": (f"unable to convert start_time {course_time.date} {course_time.startTime} and" +
                               f" end_time {course_time.date} {course_time.endTime} to scheduled events format must be mm/dd/yy and hh:mm AM/PM")
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": (f"unable to convert start_time {course_time.date} {course_time.startTime} and" +
                               f" end_time {course_time.date} {course_time.endTime} to scheduled events format must be mm/dd/yy and hh:mm AM/PM")
                })
            continue

        formatted_classes = sorted(formatted_classes)

        general = General(
            courseName=course.courseName,
            briefDescription=None,
            description=course.description,
            languages=[course.language],
            price=course.price,
            instructionTypes=instruction_types,
            remoteLink=course.onlineClassLink if course.onlineClassLink else None,
            address=address if address else None,
            phoneNumber=os.getenv("COMPANY_PHONE"),
            email=os.getenv("COMPANY_EMAIL"),
            maxStudents=20,
            enrollable=False,
            waitlist=True,
            waitlistLimit=20,
            allowCash=True,
            courseCode=course.code,
            instructors=instructors,
            certificate=True
        )

        created = await create_course(
            general=general,
            user=user,
            course_id=course_id,
            classes_in_series=len(formatted_classes),
            active=False,
            first_class_dtm=formatted_classes[0][0],
            frequency={"frequency_type": "days"},
            schedule=formatted_classes,
            is_complete=False
        )

        if not created:
            if series:
                failed_courses.append({
                    "seriesName": course.courseName,
                    "reason": "Failed to create series"
                })
            else:
                failed_courses.append({
                    "courseName": course.courseName,
                    "reason": "Failed to create course"
                })
            continue

        course_ids.append(course_id)

    return (course_ids, failed_courses)


@router.post(
    "/import/courses",
    description="Route to import courses to system",
    response_model=import_courses.Output,
    response_model_exclude_unset=True
)
async def import_courses_route(content: import_courses.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        failed_courses = []
        failed_bundles = []

        succeeded = 0
        courses = []
        if content.courses:
            courses.extend(content.courses)
        if content.series:
            courses.extend(content.series)

        if courses:
            course_ids, failed_create_courses = await __create_courses(courses=courses, user=user, series=True if content.series else False)
            if failed_create_courses:
                failed_courses.append(failed_create_courses)
            succeeded += len(course_ids)

        if content.bundles:
            for bun in content.bundles:
                if not bun.courses:
                    failed_bundles.append({
                        "bundleName": bun.bundle.name,
                        "reason": "No courses provided"
                    })
                    continue

                if not bun.bundle.price and not isinstance(bun.bundle.price, (int, float)):
                    failed_bundles.append({
                        "bundleName": bun.bundle.name,
                        "reason": "No bundle price provided"
                    })
                    continue
                bun.bundle.price = round(bun.bundle.price, 2)

                course_ids, failed_create_courses = await __create_courses(courses=bun.courses, user=user)
                if failed_create_courses:
                    for course in failed_create_courses:
                        failed_bundles.append({
                            "bundleName": bun.bundle.name,
                            "courseName": course["courseName"],
                            "reason": course["reason"]
                        })
                    continue

                bundle_id = str(uuid.uuid4())
                bundle_input = bundle.Input(
                    bundleName=bun.bundle.name,
                    active=False,
                    maxStudents=20,
                    waitlist=False,
                    price=bun.bundle.price,
                    allowCash=True,
                    courseIds=course_ids
                )

                if not await create_bundle(
                    content=bundle_input,
                    bundle_id=bundle_id,
                    user_id=user.userId,
                    is_complete=False
                ):
                    failed_bundles.append({
                        "bundleName": bun.bundle.name,
                        "reason": "Failed to create bundle"
                    })
                    continue

        payload = {
            "succeeded": succeeded
        }
        if failed_bundles:
            payload["bundles"] = failed_bundles

        if content.courses and failed_courses:
            payload["courses"] = failed_courses

        if content.series and failed_courses:
            payload["series"] = failed_courses

        if failed_bundles or failed_courses:
            return successful_response(
                success=False,
                payload=payload
            )

        await submit_audit_record(
            route="data/import/courses",
            details=f"user {user.firstName} {user.lastName} imported courses into LMS",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("An error ocurred while uploading courses")
        return server_error(message="Failed to upload courses")


@router.get(
    "/import/students/template",
    description="Route to get excel file template to upload students",
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def download_students_template():
    try:
        return FileResponse("./src/content/imports/student_template.xlsx")
    except Exception:
        log.exception(
            "Something went wrong when trying to retrive the students template")
        return server_error(message="Something went wrong when retrieving the students template.")


@router.post(
    "/import/students/upload",
    description="Route to import excel file students to system",
    response_model=import_students.Output
)
async def import_students_route(file: UploadFile = File(None), user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not file:
        return user_error(message="File must be provided")

    required_columns = [
        "first_name",
        "last_name",
        "phone_number",
        "date_of_birth",
        "eye_color",
        "house_number",
        "street_name",
        "city",
        "state",
        "zipcode",
        "gender",
        "height"
    ]

    try:
        file_name = file.filename
        content = await file.read()
        df = pd.read_excel(BytesIO(content))
        df = df.replace(r'^\s*$', np.nan, regex=True)
        df = df.replace({np.nan: None})

        # Check for missing columns
        missing_columns = [
            col for col in required_columns if col not in df.columns]
        if missing_columns:
            return user_error(
                message=f"Missing columns: {', '.join(missing_columns)}"
            )

        json_data = df.to_dict(orient='records')
        if not json_data:
            return user_error(
                message="Sheet is formatted incorrectly please fix and reupload."
            )

        json_data = [d for d in json_data if not all(
            v == '' or not v or v == ' ' for v in d.values())]

        missing_values = []
        for idx, row in enumerate(json_data):
            for col in required_columns:
                if not row.get(col):
                    missing_values.append(f"\nrow: {idx+1} col: {col}")
        # Check for missing values
        if missing_values:
            return user_error(
                message=f"Missing values in required columns: {', '.join(missing_values)}"
            )

        created_students = []

        for student in json_data:
            try:
                dob = student.get("date_of_birth").strftime('%m/%d/%Y')
                dob = datetime.strptime(dob, "%m/%d/%Y")
            except Exception:
                try:
                    dob = student.get("date_of_birth").strftime('%m-%d-%Y')
                    dob = datetime.strptime(dob, '%m-%d-%Y')
                except Exception:
                    log.exception("Failed because of datetime format")
                    created_students.append({
                        "failed": True,
                        "reason": "Invalid date_of_birth format must be mm/dd/yyyy",
                        "headShot": None,
                        "firstName": student.get("first_name"),
                        "lastName": student.get("last_name"),
                        "dob": str(student.get("date_of_birth")) if student.get("date_of_birth") else None,
                        "email": student.get("email"),
                        "phoneNumber": str(student.get("phone_number"))
                    })
                    continue

            height = student.get("height").split("'")
            feet = int(height[0])
            inches = int(height[1].replace(" ", "").replace('"', ''))

            if isinstance(student.get("zipcode"), str):
                try:
                    student["zipcode"] = int(student["zipcode"])
                except Exception:
                    log.exception("Failed to convert zipcode to int")
                    created_students.append({
                        "failed": True,
                        "reason": "Invalid zipcode format must be an integer",
                        "headShot": None,
                        "firstName": student.get("first_name"),
                        "lastName": student.get("last_name"),
                        "dob": str(student.get("date_of_birth")) if student.get("date_of_birth") else None,
                        "email": student.get("email"),
                        "phoneNumber": str(student.get("phone_number"))
                    })
                    continue

            address = ""
            if student.get('house_number'):
                if isinstance(student["house_number"], float):
                    student["house_number"] = int(student["house_number"])
                student["house_number"] = str(student["house_number"])
                address += student["house_number"]
            if student.get("street_name"):
                address += f" {student['street_name']}"
            if student.get("apt_suite"):
                address += f" {student['apt_suite']}"

            if student.get("phone_number"):
                if isinstance(student["phone_number"], str):
                    student["phone_number"] = ''.join(
                        e for e in student["phone_number"] if e.isalnum())
                else:
                    try:
                        str(int(student.get("phone_number")))
                    except Exception:
                        log.exception("Failed to convert zipcode to int")
                        created_students.append({
                            "failed": True,
                            "reason": "Invalid phone-number format must be an integer Ex: 1234567890",
                            "headShot": None,
                            "firstName": student.get("first_name"),
                            "lastName": student.get("last_name"),
                            "dob": str(student.get("date_of_birth")) if student.get("date_of_birth") else None,
                            "email": student.get("email"),
                            "phoneNumber": str(student.get("phone_number"))
                        })
                        continue

            newUser = {
                "user_id": str(uuid.uuid4()),
                "first_name": student.get("first_name"),
                "middle_name": student.get("middle_name"),
                "last_name": student.get("last_name"),
                "suffix": student.get("suffix"),
                "email": student.get("email"),
                "phone_number": str(int(student.get('phone_number'))) if student.get('phone_number') else None,
                "dob": dob,
                "eye_color": student.get("eye_color"),
                "height": (feet * 12) + inches,
                "gender": student.get("gender"),
                "head_shot": None,
                "photo_id": None,
                "other_id": None,
                "photo_id_photo": None,
                "other_id_photo": None,
                "password": pbkdf2_sha256.hash(generate_random_code(12)),
                "time_zone": 'EST',
                "create_dtm": datetime.utcnow(),
                "modify_dtm": datetime.utcnow(),
                "active": True,
                "text_notif": True,
                "email_notif": False,
                "expiration_date": None,
                "address": address if address else None,
                "city": student.get("city"),
                "state": student.get("state"),
                "zipcode": int(student.get('zipcode'))
            }

            created_user = await create_user(newUser=newUser)
            if isinstance(created_user, str):
                found_student = await get_user(phoneNumber=str(student.get('phone_number')))
                headshot = None
                if found_student:
                    headshot = found_student.headShot

                created_students.append({
                    "failed": True,
                    "reason": f"{created_user}.",
                    "headShot": headshot,
                    "firstName": student.get("first_name"),
                    "lastName": student.get("last_name"),
                    "dob": str(dob),
                    "email": student.get("email"),
                    "phoneNumber": str(student.get("phone_number"))
                })
                continue

            if not created_user:
                created_students.append({
                    "failed": True,
                    "reason": "Unable to create user in LMS, manually create.",
                    "headShot": None,
                    "firstName": student.get("first_name"),
                    "lastName": student.get("last_name"),
                    "dob": str(dob),
                    "email": student.get("email"),
                    "phoneNumber": str(student.get("phone_number"))
                })
                continue

            if not await manage_user_roles(roles=['student'], user_id=newUser["user_id"], action="add"):
                log.exception("Failed to add role to user")

            created_students.append({
                "failed": False,
                "userId": newUser["user_id"],
                "headShot": newUser.get("head_shot"),
                "firstName": student.get("first_name"),
                "middleName": student.get("middle_name"),
                "lastName": student.get("last_name"),
                "suffix": student.get("suffix"),
                "email": student.get("email"),
                "phoneNumber": newUser.get("phone_number"),
                "dob": str(newUser.get("dob")),
                "eyeColor": student.get("eye_color"),
                "houseNumber": student.get("house_number"),
                "streetName": student.get("street_name"),
                "aptSuite": student.get("apt_suite"),
                "city": newUser.get("city"),
                "state": newUser.get("state"),
                "zipcode": newUser.get("zipcode"),
                "gender": student.get("gender"),
                "height": student.get("height")
            })

        await submit_audit_record(
            route="data/import/students/upload",
            details=f"user {user.firstName} {user.lastName} imported students into LMS",
            user_id=user.userId
        )
        return successful_response(
            payload={
                "fileName": file_name,
                "students": created_students
            }
        )

    except Exception:
        log.exception("An error ocurred while uploading students")
        return server_error(message="Failed to upload students")


@router.post(
    "/import/students",
    description="Route to import excel file certs to system",
    response_model=import_students.Output
)
async def import_students_upload(content: import_students.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        # Prepare data for upload
        max_length = len(content.students)
        failed_upload = []

        converted_students = []
        for idx, student in enumerate(content.students):
            student_copy = camel_to_snake(student.dict())
            student_copy["apt_suite"] = str(student_copy.get(
                "apt_suite")) if student_copy.get("apt_suite") else None
            if student_copy.get("failed"):
                failed_upload.append({
                    "reason": student_copy.get("reason", "Student previously failed to upload to LMS"),
                    "userId": student.userId,
                    "firstName": student.firstName,
                    "lastName": student.lastName,
                    "dob": student.dob,
                    "phoneNumber": student.phoneNumber,
                    "email": student.email
                })
                continue

            student_copy["upload_info"] = {
                "uploader": user.email,
                "position": idx + 1,
                "max": max_length,
                "upload_type": "student",
                "file_name": content.fileName
            }

            converted_students.append(student_copy)

        if os.getenv("ENVIRONMENT", "prod").lower() == "prod":
            converted_students = json.dumps(
                converted_students, default=datetime_serializer)

            published = redis_client.publish(
                os.getenv("TRAINING_CONNECT_QUEUE", 'training_connect_queue'),
                converted_students
            )
            if not published:
                raise Exception("Failed to post data to redis")

        if failed_upload:
            return successful_response(
                success=False,
                payload=failed_upload,
                message="Import started."
            )

        await submit_audit_record(
            route="data/import/students",
            details=f"user {user.firstName} {user.lastName} imported students into training connect",
            user_id=user.userId
        )
        return successful_response(
            message="Import started."
        )

    except Exception:
        log.exception(
            "An error occured while uploading students to training connect")
        return server_error(
            message="Unable to import students"
        )
