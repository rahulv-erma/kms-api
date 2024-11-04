from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse, Response
import os
import uuid
import datetime
from typing import List, Union, Optional
from io import BytesIO
import json

from src import log, img_handler
from src.api.lib.auth.auth import AuthClient
from src.utils.image import is_valid_image, resize_image
from src.database.sql.course_functions import (
    list_courses,
    list_bundles,
    search_courses,
    assign_course,
    get_course,
    delete_course,
    create_course,
    create_bundle,
    get_bundle,
    get_total_course_schedule,
    update_course,
    update_bundle,
    get_content,
    find_class_time,
    update_schedule,
    check_course_registration,
    check_bundle_registration,
    validate_prerequisites,
    update_enrollment,
    unenroll_user,
    assign_bundle,
    set_course_picture,
    upload_course_content,
    publish_content,
    delete_content,
    create_course_certificate,
    delete_bundle,
    mark_class_as_complete,
    mark_course_as_complete,
    mark_bundle_as_complete
)
from src.database.sql.user_functions import (
    get_instructors,
    get_students,
    get_user,
    get_user_roles,
    get_course_students
)
from src.database.sql.audit_log_functions import submit_audit_record
from src.api.lib.base_responses import successful_response, server_error, user_error
from src.api.api_models import global_models, pagination
from src.api.api_models.courses import (
    course_update,
    bundle_update,
    list_courses_model,
    search,
    enroll,
    delete,
    create,
    catalog,
    bundle,
    load_course_model,
    content_list,
    schedule_verify,
    schedule_update,
    list_all,
    enroll_update,
    unenroll_course,
    unenroll_bundle,
    upload,
    list_bundles_model,
    schedule_list,
    content_update,
    course_details,
    bundle_details,
    complete
)
from src.modules.create_frequency import create_frequency
from src.modules.create_schedule import create_schedule
from src.modules.save_content import save_content
from src.utils.check_overlap import check_overlap
from src.modules.notifications import (
    instructor_enroll_notification,
    student_enroll_notification,
    student_bundle_enroll_notification,
    self_bundle_enroll_notification,
    self_enroll_notification,
    scheduled_class_update_notifcation,
    canceled_course_notification,
    enrollment_update_notification,
    remove_enrollment_update_notification
)

router = APIRouter(
    prefix="/courses",
    tags=["Courses"],
    responses={404: {"description": "Details not found"}}
)


@router.get(
    "/list",
    description="Route to list all courses",
    response_model=list_courses_model.CoursesOutput,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def course_list(ignore_bundle: bool = False, page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        courses, total_pages = await list_courses(ignore_bundle=ignore_bundle, page=page, pageSize=pageSize)
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        return successful_response(
            payload={
                "courses": courses,
                "pagination": pg.dict()
            }
        )
    except Exception:
        log.exception("Failed to get list of all courses")
        return server_error(
            message="Failed to get courses"
        )


# TODO: this needs a model
@router.post(
    "/search",
    description="Route to search for courses",
    response_model=search.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def course_search(content: search.Input, page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        found, total_pages = await search_courses(course_bundle=content.courseBundle, course_name=content.courseName, page=page, pageSize=pageSize)
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        payload = {
            "pagination": pg.dict()
        }
        if content.courseBundle:
            payload["bundles"] = found

        if content.courseName:
            payload["courses"] = found
        return successful_response(
            payload=payload
        )

    except Exception:
        log.exception("Failed to get list of all courses")
        return server_error(
            message="Failed to get courses"
        )


# TODO: this needs a model
@router.post(
    "/search/catalog",
    description="Route to search for courses",
    response_model=search.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def course_catalog_search(content: search.Input, page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        found, total_pages = await search_courses(
            course_bundle=content.courseBundle,
            course_name=content.courseName,
            catalog=True, page=page,
            pageSize=pageSize
        )
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        payload = {
            "pagination": pg.dict()
        }
        if content.courseBundle:
            payload["bundles"] = found

        if content.courseName:
            payload["courses"] = found
        return successful_response(
            payload=payload
        )

    except Exception:
        log.exception("Failed to get list of all courses")
        return server_error(
            message="Failed to get courses"
        )


@router.post(
    "/assign/instructor/{courseId}",
    description="Route to assign an instructor to a course",
    response_model=enroll.Output
)
async def assign_instructors(
    courseId: str,
    content: enroll.InstructorInput,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        assigned = await assign_course(course_id=courseId, instructors=content.instructors)
        if not assigned:
            return server_error(message="Failed to assign instructors to course")

        instructors = []
        user_ids = []
        for instructor in content.instructors:
            found_user = await get_user(user_id=instructor.userId)
            if found_user:
                instructors.append(found_user)
                user_ids.append(instructor.userId)

        await instructor_enroll_notification(users=instructors, course_id=courseId)

        await submit_audit_record(
            route="courses/assign/instructor/courseId",
            details=f"Assigned instructors {','.join(user_ids)} to course {courseId}",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to assign instructors to course")
        return server_error(
            message="Failed to assign instructors to course"
        )


@router.post(
    "/enroll/student/{courseId}",
    description="Route to enroll students in a course",
    response_model=enroll.Output
)
async def enroll_students(
    courseId: str,
    content: enroll.StudentCourseInput,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        failed = []
        students = []
        user_ids = []
        for student in content.students:
            found_student = await get_user(student.userId)
            if not found_student:
                failed.append(
                    f" Unable to find student with user_id {student.userId}")
                continue
            assigned = await assign_course(course_id=courseId, students=[student])
            if not assigned:
                failed.append(
                    f" Unable to register {found_student.firstName} {found_student.lastName} for course")
                continue

            students.append(found_student)
            user_ids.append(student.userId)

        await student_enroll_notification(users=students, course_id=courseId)

        await submit_audit_record(
            route="courses/enroll/students/courseId",
            details=f"Enrolled students {','.join(user_ids)} in course {courseId}",
            user_id=user.userId
        )
        if failed:
            return successful_response(success=False, payload=failed)
        return successful_response()

    except Exception:
        log.exception("Failed to enroll students to course")
        return server_error(
            message="Failed to enroll students to course"
        )


@router.post(
    "/bundle/enroll/{bundleId}",
    description="Route to enroll yourself into a bundle",
    response_model=enroll.Output
)
async def enroll_bundle_self(
    bundleId: str,
    content: enroll.SelfRegistration,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        register_details = await check_bundle_registration(bundle_id=bundleId)
        if not register_details:
            return server_error(
                message="Failed to check user registration"
            )

        if isinstance(register_details, str):
            return user_error(
                message=register_details
            )

        if register_details["complete"]:
            return user_error(
                message="Bundle has been marked as complete and can not be registered to"
            )

        if not register_details["enrollable"]:
            return user_error(
                message="Bundle is not enrollale"
            )

        registration_status = None
        if not register_details["isFull"]:
            registration_status = 'enrolled'

        if register_details['waitlist'] and register_details["isFull"]:
            registration_status = 'waitlist'

        # if register_details["pending"]:
        #     registration_status = 'pending'

        student = enroll.StudentPayload(
            userId=user.userId,
            registrationStatus=registration_status,
            userPaid=content.userPaid,
            usingCash=content.usingCash,
            denialReason=None
        )

        assigned = await assign_bundle(bundle_id=bundleId, students=[student])
        if not assigned:
            return server_error(message=f"Failed to assign {student.userId} to enroll in bundle")

        await self_bundle_enroll_notification(users=[user], bundle_id=bundleId)

        return successful_response()

    except Exception:
        log.exception("Failed to enroll self to bundle")
        return server_error(
            message="Failed to enroll self to bundle"
        )


@router.post(
    "/enroll/{courseId}",
    description="Route to enroll self to a course",
    response_model=enroll.Output
)
async def enroll_self(
    courseId: str,
    content: enroll.SelfRegistration,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        register_details = await check_course_registration(course_id=courseId)
        if not register_details:
            return server_error(
                message="Failed to check user registration"
            )
        if isinstance(register_details, str):
            return user_error(
                message=register_details
            )

        if register_details["complete"]:
            return user_error(
                message="Course has been marked as complete and can not be registered to"
            )

        if not register_details["enrollable"]:
            return user_error(
                message="Course is not enrollale"
            )

        registration_status = None
        if not register_details["isFull"]:
            registration_status = 'enrolled'

        if register_details['waitlist'] and register_details["isFull"]:
            registration_status = 'waitlist'

        # if register_details["pending"]:
        #     registration_status = 'pending'

        student = enroll.StudentPayload(
            userId=user.userId,
            registrationStatus=registration_status,
            userPaid=content.userPaid,
            usingCash=content.usingCash,
            denialReason=None
        )

        assigned = await assign_course(course_id=courseId, students=[student])
        if not assigned:
            return server_error(message=f"Failed to assign {student.userId} to enroll in course")

        await self_enroll_notification(user=user, course_id=courseId, registration_status=registration_status)
        return successful_response()
    except Exception:
        log.exception("Failed to assign student to course")
        return server_error(
            message="Failed to assign student to course"
        )


@router.post(
    "/delete",
    description="Route to delete courses",
    response_model=delete.Output
)
async def course_delete(
    content: delete.Input,
    bypassChecks: bool = False,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        for courseId in content.courseIds:
            course = await get_course(course_id=courseId)
            if not course[0] or not course[0].get("courseName"):
                return user_error(
                    message=f"No course found with course_id {courseId}"
                )
            course = course[0]
            students = await get_students(course_id=courseId)
            instructors = await get_instructors(course_id=courseId)

            if not bypassChecks:
                # check if course is active
                if course["active"]:
                    return user_error(
                        message=f"Course {courseId} is active"
                    )
                if students:
                    return user_error(
                        message=f"Course {courseId} has students enrolled"
                    )
                # check if course is enrollable
                if course["enrollable"]:
                    return user_error(
                        message=f"Course {courseId} is enrollable"
                    )
            first_class_dtm = course["startDate"]
            # if all checks pass delete else error
            if not await delete_course(course_id=courseId):
                return server_error(
                    message="Failed to delete course {courseId}"
                )
            # delete course content folder
            if course['coursePicture']:
                os.remove(
                    f'/source/src/content/courses/{course["coursePicture"]}')

            canceled_course_notification(
                course=course,
                students=students,
                instructors=instructors,
                first_class_dtm=datetime.datetime.strptime(
                    first_class_dtm, "%m/%d/%Y %I:%M %p")
            )
        await submit_audit_record(
            route="courses/delete",
            details=f"Courses {', '.join(content.courseIds)} have been deleted",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception(f"Failed to delete course {courseId}")
        return server_error(
            message=f"Failed to delete course {courseId}"
        )


@router.post(
    "/bundle/delete",
    description="Route to delete bundles",
    response_model=delete.Output
)
async def bundle_delete(
    content: delete.Input,
    bypassChecks: bool = False,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        for bundleId in content.bundleIds:
            bundle = await get_bundle(bundle_id=bundleId)
            if not bundle[0] or not bundle[0].get("bundleName"):
                return user_error(
                    message=f"No bundle found with bundle_id {bundleId}"
                )
            bundle = bundle[0]
            students = await get_students(bundle_id=bundleId)
            instructors = await get_instructors(bundle_id=bundleId)

            if not bypassChecks:
                # check if course is active
                if bundle["active"]:
                    return user_error(
                        message=f"bundle {bundleId} is active"
                    )
                if students:
                    return user_error(
                        message=f"bundle {bundleId} has students enrolled"
                    )
                # check if bundle is enrollable
                if bundle["enrollable"]:
                    return user_error(
                        message=f"bundle {bundleId} is enrollable"
                    )
            for bc in bundle["courses"]:
                course = await get_course(course_id=bc["courseId"])
                course = course[0]
                first_class_dtm = course["startDate"]
                # if all checks pass delete else error
                if not await delete_course(course_id=bc["courseId"]):
                    return server_error(
                        message="Failed to delete course {courseId}"
                    )
                # delete course content folder
                if course['coursePicture']:
                    os.remove(
                        f'/source/src/content/courses/{course["coursePicture"]}')

                canceled_course_notification(
                    course=course,
                    students=students,
                    instructors=instructors,
                    first_class_dtm=datetime.datetime.strptime(
                        first_class_dtm, "%m/%d/%Y %I:%M %p")
                )

            if not await delete_bundle(bundle_id=bundleId):
                return server_error(message=f"Failed to delete bundle {bundleId}")
        await submit_audit_record(
            route="courses/bundle/delete",
            details=f"Bundles {', '.join(content.bundleIds)} have been deleted",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception(f"Failed to delete bundle {bundleId}")
        return server_error(
            message=f"Failed to delete bundle {bundleId}"
        )


# TODO: model needs to be updated
@router.get(
    "/load/{courseId}",
    description="Route to load an entire courses details",
    response_model=load_course_model.Output
)
async def load_course(courseId: str = None, user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not courseId:
        return user_error(
            message="Must supply a courseId"
        )
    try:
        course = await get_course(course_id=courseId)
        if not course[0] or not course[0].get("courseName"):
            return user_error(
                message=f"No course found with course_id {courseId}"
            )

        if course[0]['enrollable']:
            enrollable = await validate_prerequisites(course=course[0], user_id=user.userId)
            course[0]['enrollable'] = enrollable

        payload = {
            "course": course[0],
            "schedule": course[1]
        }

        roles = await get_user_roles(user_id=user.userId)
        for role in roles:
            if role["roleName"] in ["admin", "superuser"]:
                students = await get_course_students(course_id=courseId)
                payload["students"] = students
                break
        return successful_response(
            payload=payload
        )
    except Exception:
        log.exception(f"Failed to load course {courseId}")
        return server_error(
            message=f"Failed to load course {courseId}"
        )


@router.post(
    "/create",
    description="Route to create a course",
    response_model=create.Output
)
async def course_create(content: create.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    frequency = create_frequency(content=content.series)
    if not frequency:
        log.exception("Failed to build frequency")
        return server_error(
            message="unable to build frequency"
        )

    schedule = create_schedule(
        frequency=frequency,
        first_class_dtm=content.series.firstClassDtm,
        classes_in_series=content.series.classesInSeries,
        class_duration=content.general.duration
    )
    if not schedule:
        log.exception("Failed to build schedule")
        return server_error(
            message="unable to build schedule"
        )

    course_id = str(uuid.uuid4())

    try:
        course = await create_course(
            general=content.general,
            schedule=schedule,
            frequency=frequency,
            user=user,
            course_id=course_id,
            classes_in_series=content.series.classesInSeries,
            active=content.active,
            first_class_dtm=datetime.datetime.strptime(
                content.series.firstClassDtm.replace('Z', '+0000'), '%Y-%m-%dT%H:%M:%S.%f%z'),
            quizzes=content.quizzes,
            surveys=content.surveys,
            certificate=content.certification.certificate
        )
        if not course:
            return server_error(
                message="unable to create course"
            )

        if content.certification.certificate:
            await create_course_certificate(
                course_id=course_id,
                certificate_id=str(uuid.uuid4()),
                certificate_name=content.certification.certificateName,
                certificate_length=json.dumps(
                    dict(content.certification.expiration)) if content.certification.expiration else None,
                certificate_template=None
            )

        await submit_audit_record(
            route="courses/create",
            details=f"User {user.firstName} {user.lastName} created course {course_id}",
            user_id=user.userId
        )
        return successful_response(
            payload={
                "courseId": course_id
            }
        )
    except Exception:
        log.exception("Failed to create course")
        return server_error(
            message="Failed to create course"
        )


@router.get(
    "/catalog",
    description="Route to list course catalog",
    response_model=catalog.CourseOutput,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def course_catalog(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        # List the courses using the list_courses function depending
        # on whether or not active/enrollment/waitlist is set to True
        courses, total_pages = await list_courses(ignore_bundle=True, enrollment=True, page=page, pageSize=pageSize)
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "courses": courses,
                "pagination": pg.dict()
            }
        )
    except Exception:
        log.exception("Failed to return course catalog")
        return server_error(
            message="Failed to get course catalog"
        )


@router.get(
    "/bundle/catalog",
    description="Route to list bundle catalog",
    response_model=catalog.BundleOutput,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def bundle_catalog(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        # List the courses using the list_courses function depending
        # on whether or not active/enrollment/waitlist is set to True
        bundles, total_pages = await list_bundles(enrollment=True, page=page, pageSize=pageSize)
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        return successful_response(
            payload={
                "bundles": bundles,
                "pagination": pg.dict()
            }
        )
    except Exception:
        log.exception("Failed to return course catalog")
        return server_error(
            message="Failed to get course catalog"
        )


@router.post(
    "/bundle/create",
    description="Route to create a course bundle",
    response_model=bundle.Output
)
async def bundle_create_route(content: bundle.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    bundle_id = str(uuid.uuid4())

    try:
        if not await create_bundle(
            content=content,
            bundle_id=bundle_id,
            user_id=user.userId
        ):
            return server_error(
                message="Failed to create bundle"
            )

        await submit_audit_record(
            route="courses/bundle/create",
            details=f"User {user.firstName} {user.lastName} created bundle {bundle_id}",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to create bundle")
        return server_error(
            message="Failed to load bundle"
        )


@router.get(
    "/bundle/list",
    description="Route to list all bundles",
    response_model=list_bundles_model.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def bundle_list(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        bundles, total_pages = await list_bundles(page=page, pageSize=pageSize)
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        return successful_response(
            payload={
                "bundles": bundles,
                "pagination": pg.dict()
            }
        )
    except Exception:
        log.exception("Failed to get list of all bundles")
        return server_error(
            message="Failed to get bundles"
        )


# TODO: this needs a response model
@router.get(
    "/bundle/load/{bundleId}",
    description="Route to create a course bundle",
    response_model=bundle.Output
)
async def load_bundle_route(bundleId: str = None, user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not bundleId:
        return user_error(
            message="No bundle id present for look up"
        )

    try:
        bundle = await get_bundle(bundle_id=bundleId)
        if not bundle[0] or not bundle[0].get("bundleName"):
            return server_error(
                message="Failed to fetch bundle"
            )

        payload = {
            "bundle": bundle[0],
            "schedule": bundle[1]
        }

        roles = await get_user_roles(user_id=user.userId)
        for role in roles:
            if role["roleName"] in ["admin", "superuser"]:
                students = await get_course_students(bundle_id=bundleId)
                payload["students"] = students
                break

        return successful_response(payload=payload)

    except Exception:
        log.exception("Failed to load course")
        return server_error(
            message="Failed to load course"
        )


@router.get(
    "/schedule",
    description="Route to get all scheduled courses",
    response_model=schedule_list.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def complete_schedule(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        schedule, total_pages = await get_total_course_schedule(page=page, pageSize=pageSize)
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        return successful_response(
            payload={
                "schedule": schedule,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception("Failed to fetch complete schedule")
        return server_error(
            message="Failed to fetch complete schedule"
        )


@router.post(
    "/schedule/verify",
    description="Route to see if schedules intertwine",
    response_model=schedule_verify.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def schedule_verify_route(content: schedule_verify.Input):
    try:
        scheduled_times = []

        for id in content.courseIds:
            course = await get_course(course_id=id)
            if not course[0] or not course[0].get("courseName"):
                return user_error(message="A course does not exist with one of the ID's provided.")

            schedule = course[1]
            course_sched = {
                "startTime": schedule[0]["startTime"],
                "endTime": schedule[0]["endTime"],
                "courseName": course[0]["courseName"],
                "courseId": course[0]["courseId"]
            }
            scheduled_times.append(course_sched)

        overlapping = []
        for schedule1 in scheduled_times:
            for schedule2 in scheduled_times:
                if schedule1 != schedule2 and check_overlap(schedule1, schedule2):
                    overlapping.append(schedule1)

        if overlapping:
            return successful_response(
                success=False,
                payload={
                    "courses": overlapping
                }
            )

        return successful_response()
    except Exception:
        log.exception("Failed to verify course schedules")
        return server_error(
            message="Failed to verify course schedules"
        )


@router.post(
    "/update",
    description="Route to get update a course",
    response_model=course_update.Output
)
async def update_course_route(content: course_update.UpdateCourseInput, user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not content.courseId:
        user_error(message="A course id must be provided to update")

    try:
        if not await update_course(content):
            return server_error(message="Failed to update course")

        await submit_audit_record(
            route="courses/update",
            details=(f"User {user.firstName} {user.lastName} updated course {content.courseId} with" +
                     f" values {json.dumps(content.dict(exclude_none=True))}"),
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to act on course update")
        return server_error(
            message="Failed to act on course update"
        )


@router.post(
    "/bundle/update",
    description="Route to get update a course bundle",
    response_model=bundle_update.Output
)
async def update_bundle_route(content: bundle_update.UpdateBundleInput, user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not content.bundleId:
        user_error(message="A bundle id must be provided to update")

    try:
        if not await update_bundle(content):
            return server_error(message="Failed to update bundle")

        await submit_audit_record(
            route="courses/bundle/update",
            details=(f"User {user.firstName} {user.lastName} updated bundle {content.bundleId} with" +
                     f" values {json.dumps(content.dict(exclude_none=True))}"),
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to act on bundle update")
        return server_error(
            message="Failed to act on bundle update"
        )


@router.get(
    "/list/all",
    description="Route to get bundles and courses for course management",
    response_model=list_all.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def manage_list(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        courses, total_pages_courses = await list_courses(page=page, pageSize=pageSize)
        bundles, total_pages_bundles = await list_bundles(page=page, pageSize=pageSize)

        pg_course = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages_courses,
            pageSize=pageSize
        )

        pg_bundle = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages_bundles,
            pageSize=pageSize
        )
        return successful_response(
            payload={
                "courses": courses,
                "coursePagination": pg_course.dict(),
                "bundles": bundles,
                "bundlePagination": pg_bundle.dict(),
            }
        )

    except Exception:
        log.exception("Failed to get courses or bundles")
        return server_error(
            message="Failed to get courses or bundles"
        )


@router.get(
    "/content/load/{fileId}",
    description="Route to load course content",
    response_class=FileResponse
)
async def load_content_get(fileId: str, uid: str, size: int = 1024, published: bool = False):
    try:
        if not img_handler.get_key(redis_key=uid):
            return user_error(
                status_code=403,
                message="Unauthorized"
            )

        content, _ = await get_content(content_id=fileId, published=published)
        if content:
            user_roles = await get_user_roles(user_id=uid)
            if not user_roles:
                raise ValueError

            if any(role["roleName"] for role in user_roles) == 'student' and not published:
                print("role name check not passed")
                # TODO: remove this later
                # return user_error(
                #     status_code=401,
                #     message="unauthorized"
                # )

        fileLocation = rf"/source/src/content/courses/{fileId}"
        if not os.path.exists(fileLocation):
            await delete_content(file_ids=[fileId])
            return server_error(message="File does not exist")

        if size and is_valid_image(fileLocation):
            image = resize_image(fileLocation, size)
            if not image:
                return server_error(message="Something went wrong resizing the image")

            if isinstance(image, str):
                return user_error(
                    message=image
                )
            output_buffer = BytesIO()
            if image.mode in ['RGBA', 'P']:
                image = image.convert('RGB')
            image.save(output_buffer, format="JPEG", quality=95)
            output_buffer.seek(0)

            return Response(content=output_buffer.getvalue(), media_type="image/jpeg")
        else:
            return FileResponse(fileLocation)
    except Exception:
        log.exception(f"Something went wrong loading content for course {id}")
        return server_error(message="Something wetn wrong when loading content")


@router.get(
    "/content/list/{courseId}",
    description="Route to list all of a courses content",
    response_model=content_list.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def list_content(courseId: str = None, page: int = None, pageSize: int = None, published: Optional[bool] = None):
    if isinstance(page, int) and page <= 0:
        page = 1

    if not courseId:
        return user_error(message="Course must be provided.")

    try:
        databaseContent, total_pages = await get_content(course_id=courseId, page=page, pageSize=pageSize, published=published)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        return successful_response(payload={"content": databaseContent, "pagination": pg.dict()})
    except Exception:
        log.exception(
            "Something went wrong when trying to load all content for a course")
        return server_error(message="Something went wrong when loading all content")


# TODO: this needs a model
@router.get(
    "/details/{courseId}",
    description="Route to list all details of a course",
    response_model=course_details.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def course_details_route(courseId: str):
    try:
        course = await get_course(course_id=courseId)
    except Exception:
        log.exception(
            "Something went wrong when trying to load all details for a course")
        return server_error(message="Something went wrong when loading all course details")

    if not course[0] or not course[0].get("courseName"):
        return server_error(message=f"Could not find any course with course_id {courseId}")

    return successful_response(payload={"course": course[0]})


# TODO: this needs a model
@router.get(
    "/bundle/details/{bundleId}",
    description="Route to list all of a bundles details",
    response_model=bundle_details.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def bundle_details_route(bundleId: str):
    try:
        bundle = await get_bundle(bundle_id=bundleId)
    except Exception:
        log.exception(
            "Something went wrong when trying to load all details for a bundle")
        return server_error(message="Something went wrong when loading all bundle details")

    if not bundle[0] or not bundle[0].get("bundleName"):
        return server_error(message=f"Could not find any bundle with bundle_id {bundleId}")

    return successful_response(payload={"bundle": bundle[0], "schedule": bundle[1]})


@router.get(
    "/enroll/update/{courseId}",
    description="Route to update status of a students enrollment",
    response_model=enroll_update.Output
)
async def enroll_update_route(
    courseId: str,
    content: enroll_update.Input,
    executer: global_models.User = Depends(AuthClient(use_auth=True))
):

    if not courseId:
        return user_error(message="Course does not exist with this ID")

    try:
        user = await get_user(user_id=content.userId)
        if not user:
            user_error(message="User does not exist")

        course = await get_course(course_id=courseId)
        if not course[0] or not course[0].get("courseName"):
            return user_error(message="Course does not exist")

        update = await update_enrollment(
            course_id=courseId,
            user_id=content.userId,
            status=content.registrationStatus,
            paid=content.paid,
            notes=content.notes
        )
        if not update:
            return server_error(message="Could not update users enrollment")

        if content.registrationStatus:
            enrollment_update_notification(
                user=user,
                course=course[0],
                new_status=content.registrationStatus
            )

        await submit_audit_record(
            route="courses/enroll/update/courseId",
            details=(f"User {executer.firstName} {executer.lastName} updated user {content.userId} enrollment" +
                     f" to {content.registrationStatus} woth paid {content.paid} for course {courseId}"),
            user_id=executer.userId
        )
        return successful_response()
    except Exception:
        log.exception(
            f"Something went wrong when trying to change user {content.userId} enrollment status")
    return server_error(message=f"Something went wrong when trying to change user {content.userId} enrollment status")


@router.get(
    "/bundle/enroll/update/{bundleId}",
    description="Route to update status of a students enrollment",
    response_model=enroll_update.Output
)
async def enroll_bundle_update_route(
    bundleId: str,
    content: enroll_update.Input,
    executer: global_models.User = Depends(AuthClient(use_auth=True))
):

    if not bundleId:
        return user_error(message="Bundle does not exist with this ID")

    try:
        user = await get_user(user_id=content.userId)
        if not user:
            user_error(message="User does not exist")

        bundle = await get_bundle(bundle_id=bundleId)
        if not bundle[0] or not bundle[0].get("bundleName"):
            return user_error(message="Bundle does not exist")

        for course in bundle[0]["courses"]:
            update = await update_enrollment(
                course_id=course["courseId"],
                user_id=content.userId,
                status=content.registrationStatus,
                paid=content.paid, notes=content.notes
            )
            if not update:
                return server_error(message="Could not update users enrollment")

        if content.registrationStatus:
            enrollment_update_notification(
                user=user,
                bundle=bundle[0],
                new_status=content.registrationStatus
            )

        await submit_audit_record(
            route="courses/bundle/enroll/update/courseId",
            details=(f"User {executer.firstName} {executer.lastName} updated user {content.userId} enrollment" +
                     f" to {content.registrationStatus} woth paid {content.paid} for bundle {bundleId}"),
            user_id=executer.userId
        )
        return successful_response()
    except Exception:
        log.exception(
            f"Something went wrong when trying to change user {content.userId} enrollment status")
    return server_error(message=f"Something went wrong when trying to change user {content.userId} enrollment status")


# TODO: this needs a model
@router.post(
    "/schedule/update",
    description="Route to update scheduled class",
    response_model=schedule_update.Output
)
async def schedule_update_route(content: schedule_update.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    new_class = None
    try:
        found_class = await find_class_time(course_id=content.courseId, series_number=content.seriesNumber)
        if not found_class:
            return user_error(message="Class does not exist")

        if found_class["is_complete"]:
            return user_error(message="Class is already complete")

        start_dtm = datetime.datetime.strptime(
            content.startTime.replace('Z', '+0000'), '%Y-%m-%dT%H:%M:%S.%f%z')
        end_dtm = start_dtm + datetime.timedelta(minutes=content.duration)

        new_class = {
            "is_complete": False,
            "course_id": content.courseId,
            "series_number": content.seriesNumber,
            "start_dtm": start_dtm,
            "end_dtm": end_dtm
        }
        updated = await update_schedule(new_class=new_class)
        if not updated:
            return server_error(message="Failed to update scheduled class")

        users = []
        instructors = await get_instructors(content.courseId)
        if instructors:
            users.extend(instructors)
        students = await get_students(content.courseId)
        if students:
            users.extend(students)

        course = await get_course(course_id=content.courseId)
        course = course[0]
        scheduled_class_update_notifcation(
            users=users, new_class=new_class, original_class=found_class, course=course)

        await submit_audit_record(
            route="courses/schedule/update",
            details=(f"User {user.firstName} {user.lastName} updated schedule details" +
                     f" {json.dumps(found_class)} to {json.dumps(new_class)} for course {content.courseId}"),
            user_id=user.userId
        )

    except Exception:
        log.exception("Something went wrong when trying to update class time")
        return server_error(message="Something went wrong when trying to update class time")

    return successful_response(payload={"class": new_class})


# TODO: this needs to be tested
@router.post(
    "/unenroll/{courseId}/{userId}",
    description="Route to unenroll a user from a course",
    response_model=unenroll_course.Output
)
async def unenroll_course_route(courseId: str, userId: str, executer: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        user = await get_user(user_id=userId)
        if not user:
            return user_error(message="User does not exist")

        course = await get_course(course_id=courseId, full_details=False)
        if not course[0] or not course[0].get("courseName"):
            return user_error(message="Course does not exist")

        unenrolled = await unenroll_user(course_id=courseId, user_id=userId)
        if not unenrolled:
            return server_error(message="Failed to unenroll user from course")

        remove_enrollment_update_notification(user=user, course=course[0])
        await submit_audit_record(
            route="courses/unenroll/courseId/userId",
            details=f"User {executer.firstName} {executer.lastName} unenrolled user {userId} from course {courseId}",
            user_id=executer.userId
        )
    except Exception:
        log.exception(
            f"Something went wrong when trying to unenroll user: {userId} from course {courseId}")
        return server_error(message=f"Something went wrong when trying to unenroll user: {userId} from course {courseId}")

    return successful_response()


# TODO: this needs to be tested
@router.post(
    "/bundle/unenroll/{bundleId}/{userId}",
    description="Route to unenroll a user from a bundle",
    response_model=unenroll_bundle.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def unenroll_bundle_route(bundleId: str, userId: str, executer: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        user = await get_user(user_id=userId)
        if not user:
            return user_error(message="User does not exist")

        bundle = await get_bundle(bundle_id=bundleId)
        if not bundle[0] or not bundle[0].get("bundleName"):
            return user_error(message="Bundle does not exist")

        unenrolled = await unenroll_user(bundle_id=bundleId, user_id=userId)
        if not unenrolled:
            return server_error(message="Failed to unenroll user from bundle")

        remove_enrollment_update_notification(user=user, bundle=bundle[0])
        await submit_audit_record(
            route="courses/bundle/unenroll/courseId/userId",
            details=f"User {executer.firstName} {executer.lastName} unenrolled user {userId} from bundle {bundleId}",
            user_id=executer.userId
        )
    except Exception:
        log.exception(
            f"Something went wrong when trying to unenroll user: {userId} from bundle {bundleId}")
        return server_error(message=f"Something went wrong when trying to unenroll user: {userId} from bundle {bundleId}")

    return successful_response()


@router.post(
    "/bundle/enroll/student/{bundleId}",
    description="Route to enroll students in a bundle",
    response_model=enroll.Output
)
async def enroll_bundle_students(bundleId: str, content: enroll.StudentBundleInput, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        failed = []
        students = []
        user_ids = []
        for student in content.students:
            found_student = await get_user(student.userId)
            if not found_student:
                failed.append(
                    f" Unable to find student with user_id {student.userId}")
                continue

            assigned = await assign_bundle(bundle_id=bundleId, students=content.students)
            if not assigned:
                failed.append(
                    f" Unable to register {found_student.firstName} {found_student.lastName} for bundle")
                continue

            students.append(found_student)
            user_ids.append(student.userId)

        await student_bundle_enroll_notification(users=students, bundle_id=bundleId)
        await submit_audit_record(
            route="courses/bundle/enroll/student/bundleId",
            details=f"User {user.firstName} {user.lastName} enrolled users {', '.join(content.students)} to bundle {bundleId}",
            user_id=user.userId
        )

        if failed:
            return successful_response(success=False, payload=failed)

        return successful_response()
    except Exception:
        log.exception("Failed to enroll students to bundle")
        return server_error(
            message="Failed to enroll students to bundle"
        )


@router.post(
    "/content/upload/{courseId}",
    description="Route to upload a course picture/content",
    response_model=upload.Output
)
async def upload_course_content_route(
    courseId: str,
    coursePicture: Union[UploadFile, None] = File(None),
    content: List[Union[UploadFile, None]] = File(None),
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        course = await get_course(course_id=courseId)
        if not course[0] or not course[0].get("courseName"):
            return user_error(
                message=f"No course with id {courseId} exists"
            )

        if coursePicture:
            saved = await save_content(
                types="courses",
                file=coursePicture,
                content_types=['image/png', 'image/jpeg', 'image/jpg']
            )
            if not saved["success"]:
                return user_error(
                    message=saved["reason"]
                )

            picture_set = await set_course_picture(course_id=courseId, course_picture=saved["file_id"], user=user)
            if not picture_set:
                return server_error(message="Failed to set course picture")

        if content:
            successfully_saved = []
            for course_content in content:
                saved = await save_content(
                    types="courses",
                    file=course_content,
                    content_types=[
                        'application/pdf',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/msword',
                        'application/vnd.ms-powerpoint',
                        'image/png',
                        'image/jpeg',
                        'image/jpg',
                        'text/csv',
                    ]
                )
                if saved["success"]:
                    successfully_saved.append({
                        "content_name": saved["file_name"],
                        "content_id": saved["file_id"],
                    })
                else:
                    return user_error(
                        message=f"Failed to upload file {course_content.filename} for {saved['reason']}"
                    )

            if not await upload_course_content(course_id=courseId, content=successfully_saved, user=user):
                return server_error(message="Failed to save content for course")

        await submit_audit_record(
            route="courses/upload/content/courseId",
            details=f"User {user.firstName} {user.lastName} uploaded content for course {courseId}",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to add content to course")
        return server_error(
            message="Failed to add content to course"
        )


@router.post(
    "/content/update/{courseId}",
    description="Route to update a course content",
    response_model=content_update.Output
)
async def update_course_content_route(
    courseId: str,
    content: content_update.UpdateInput,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        course = await get_course(course_id=courseId)
        if not course[0] or not course[0].get("courseName"):
            return user_error(
                message=f"No course with id {courseId} exists"
            )

        if not await publish_content(user_id=user.userId, course_id=courseId, file_ids=content.fileIds, publish=content.publish):
            return server_error(message="Failed to update content")

        await submit_audit_record(
            route="courses/update/content/courseId",
            details=(f"User {user.firstName} {user.lastName} updated content {', '.join(content.fileIds)} to" +
                     f" published status {content.publish} for course {courseId}"),
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to change content publish status")
        return server_error(
            message="Failed to change content publish status"
        )


@router.post(
    "/content/delete/{courseId}",
    description="Route to delete a courses content",
    response_model=content_update.Output
)
async def delete_course_content_route(
    courseId: str,
    content: content_update.DeleteInput,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        course = await get_course(course_id=courseId)
        if not course[0] or not course[0].get("courseName"):
            return user_error(
                message=f"No course with id {courseId} exists"
            )

        if not await delete_content(course_id=courseId, file_ids=content.fileIds):
            return server_error(message="Failed to delete content")

        await submit_audit_record(
            route="courses/delete/content/courseId",
            details=f"User {user.firstName} {user.lastName} deleted content {', '.join(content.fileIds)} from course {courseId}",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to delete content")
        return server_error(
            message="Failed to delete content"
        )


@router.post(
    "/complete/{courseId}",
    description="Route to mark a course as complete",
    response_model=complete.Output
)
async def complete_course_route(
    courseId: str,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        course = await get_course(course_id=courseId)
        if not course[0] or not course[0].get("courseName"):
            return user_error(
                message=f"No course with id {courseId} exists"
            )

        await mark_class_as_complete(course_id=courseId)
        await mark_course_as_complete(course_id=courseId)

        await submit_audit_record(
            route="courses/complete/courseId",
            details=f"User {user.firstName} {user.lastName} marked course {courseId} as complete",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to mark complete course as complete")
        return server_error(
            message="Failed to mark complete course as complete"
        )


@router.post(
    "/schedule/complete/{courseId}/{seriesNumber}",
    description="Route to mark a class as complete",
    response_model=complete.Output
)
async def complete_class_route(
    courseId: str,
    seriesNumber: int = None,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        course = await get_course(course_id=courseId)
        if not course[0] or not course[0].get("courseName"):
            return user_error(
                message=f"No course with id {courseId} exists"
            )

        await mark_class_as_complete(course_id=courseId, series_number=seriesNumber)

        await submit_audit_record(
            route="courses/schedule/complete/courseId",
            details=f"User {user.firstName} {user.lastName} marked series number {seriesNumber} as complete for course {courseId}",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to mark complete course as complete")
        return server_error(
            message="Failed to mark complete course as complete"
        )


@router.post(
    "/bundle/complete/{bundleId}",
    description="Route to mark a bundle as complete",
    response_model=complete.Output
)
async def complete_bundle_route(
    bundleId: str,
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        bundle = await get_bundle(bundle_id=bundleId)
        if not bundle[0] or not bundle[0].get("bundleName"):
            return user_error(
                message=f"No bundle with id {bundleId} exists"
            )

        for course in bundle[0]['courses']:
            await mark_course_as_complete(course_id=course["courseId"])
            await mark_class_as_complete(course_id=course["courseId"])

        await mark_bundle_as_complete(bundle_id=bundleId)

        await submit_audit_record(
            route="courses/bundle/complete/bundleId",
            details=f"User {user.firstName} {user.lastName} marked bundle {bundleId} as complete",
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception("Failed to mark complete bundle as complete")
        return server_error(
            message="Failed to mark complete bundle as complete"
        )
