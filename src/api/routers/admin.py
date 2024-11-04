import datetime
from fastapi import APIRouter, Depends
from passlib.hash import pbkdf2_sha256
import json

from src import log
from src.api.lib.auth.auth import AuthClient
from src.database.sql.user_functions import (
    get_roles,
    manage_user_roles,
    delete_users,
    deactivate_user,
    activate_user,
    update_user,
    get_user,
    delete_user_certificates,
    find_certificate
)
from src.database.sql.course_functions import (
    get_course,
    get_course_certificate
)
from src.database.sql.audit_log_functions import submit_audit_record
from src.api.lib.base_responses import successful_response, server_error, user_error
from src.api.api_models.admin import roles, assign, activate, user_delete_model, delete_certificates, gen_certificate
from src.api.api_models.pagination import PaginationOutput
from src.api.api_models import global_models
from src.api.api_models.users import update
from src.utils.certificate_generation import generate_certificate, save_user_certificate
from src.utils.generate_random_code import generate_random_code

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    responses={404: {"description": "Details not found"}}
)


@router.get(
    "/roles/list",
    description="Route to list all roles",
    response_model=roles.ListOutput,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def list_roles(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        roles, total_pages = await get_roles(page=page, pageSize=pageSize)
        if not roles:
            return server_error(message="No roles found.")

        pagination = PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        return successful_response(
            payload={
                "roles": roles,
                "pagination": pagination.dict()
            }
        )
    except Exception:
        log.exception("Failed to get list of all roles")
        return server_error(
            message="Failed to get roles"
        )


@router.post(
    "/roles/manage/{userId}",
    description="Route to manage roles to a user",
    response_model=assign.Output
)
async def roles_manage(userId: str, content: assign.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        if content.add:
            if not await manage_user_roles(roles=content.add, user_id=userId, action="add"):
                return user_error(
                    message="Roles or user do not exist"
                )
        if content.remove:
            if not await manage_user_roles(roles=content.remove, user_id=userId, action="remove"):
                return user_error(
                    message="Roles or user do not exist"
                )

        await submit_audit_record(
            route="admin/roles/manage/userId",
            details=(f"Update to roles for user {user.firstName} {user.lastName} action" +
                     f" {'add' if content.add else 'remove'} Added:" +
                     f" {content.add if content.add else 'None'} Removed: {content.remove if content.remove else 'None'}"),
            user_id=user.userId
        )
        return successful_response()
    except Exception:
        log.exception(f"Failed to assign roles to user {userId}")
        return server_error(
            message=f"Failed to assign roles to user {userId}"
        )


# TODO: needs response model
@router.post(
    "/users/certificates/generate",
    description="Route to generate a certificate for course",
    response_model=gen_certificate.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def generate_certificate_route(content: gen_certificate.Input):
    failed_users = []
    try:
        if not content.courseId and not content.certificateName:
            return user_error(message="Either courseId or certificateName must be provided")

        if content.courseId and content.certificateName:
            return user_error(message="Either courseId or certificateName not both")

        if content.courseId:
            course = await get_course(course_id=content.courseId)
            if not course[0]:
                return user_error(message="Course does not exist")

        if content.courseId:
            certificate = await get_course_certificate(course_id=content.courseId)

        for user_id in content.userIds:
            user = await get_user(user_id=user_id)
            if not user:
                failed_users.append(
                    f"User not found for user id {user_id}"
                )

            # TODO: check if user already has a certificate for this course
            if content.courseId:
                found = await find_certificate(user_id=user_id, course_id=content.courseId)
                if found:
                    failed_users.append(
                        f"User {user.firstName} {user.lastName} already has a certificate for {course[0]['courseName']}"
                    )
                    continue

                cert = await generate_certificate(user=user, course=course[0], certificate=certificate)
                if not cert:
                    failed_users.append(
                        f"Failed to generate certificate for user {user.firstName} {user.lastName}"
                    )
                    continue
            else:
                expiration_date = None
                if content.expirationDate:
                    try:
                        expiration_date = datetime.datetime.strptime(
                            content.expirationDate, "%m/%d/%Y")
                    except Exception:
                        failed_users.append(
                            f"Invalid date format {content.expirationDate} must be mm/dd/yyyy"
                        )
                        continue

                found = await find_certificate(user_id=user_id, certificate_name=content.certificateName)
                if found:
                    failed_users.append(
                        f"User {user.firstName} {user.lastName} already has a certificate for {content.certificateName}"
                    )
                    continue
                await save_user_certificate(
                    certificate_number=generate_random_code(15),
                    completion_date=datetime.datetime.utcnow(),
                    user=user,
                    expiration_date=expiration_date,
                    certificate_name=content.certificateName
                )

        if not failed_users:
            return successful_response()

        await submit_audit_record(
            route="users/update/userId",
            details=(f"User {user.firstName} {user.lastName} generated certificate" +
                     f" for users {', '.join(content.userIds)} for course {content.courseId}"),
            user_id=user.userId
        )
        return successful_response(
            success=False,
            payload={
                "students": failed_users
            }
        )

    except Exception:
        log.exception("Failed to generate certificates for users")

    return server_error(
        message="Failed to generate certificates"
    )


@router.post(
    "/users/certificates/delete",
    description="Route to get delete user certificates",
    response_model=delete_certificates.Output
)
async def delete_certificate_route(content: delete_certificates.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        log.info("in route")
        deleted = await delete_user_certificates(certificate_numbers=content.certificateNumbers)
        if not deleted:
            return server_error(message="Failed to delete user certificates")

        await submit_audit_record(
            route="/users/delete/certificates",
            details=f"User {user.firstName} {user.lastName} deleted certificates {', '.join(content.certificateNumbers)}",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to delete user certificates")
        return server_error(message="Failed to delete user certificates")


@router.post(
    "/users/delete/{userId}",
    description="Route to delete users from system",
    response_model=user_delete_model.Output
)
async def delete_user_route(userId: str, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        failed_deletes = await delete_users(user_ids=[userId])
        if failed_deletes:
            return server_error(
                message="Failed to delete user"
            )

        await submit_audit_record(
            route="admin/users/delete/userId",
            details=f"User {user.firstName} {user.lastName} deleted user {userId} from lms",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to delete user from LMS")
        return server_error(
            message="Failed to delete user from LMS"
        )


@router.post(
    "/users/delete",
    description="Route to delete users from system",
    response_model=user_delete_model.Output
)
async def bulk_delete_user_route(content: user_delete_model.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        failed_deletes = await delete_users(user_ids=content.userIds)
        if failed_deletes[0] and failed_deletes[1]:
            return server_error(
                message="Failed to delete user"
            )

        await submit_audit_record(
            route="admin/users/delete",
            details=f"User {user.firstName} {user.lastName} deleted users {', '.join(content.userIds)} from lms",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to delete user from LMS")
        return server_error(
            message="Failed to delete user from LMS"
        )


@router.post(
    "/users/deactivate/{userId}",
    description="Route to deactivate user in system",
    response_model=activate.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def deactivate_user_route(userId: str, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        deactivated = await deactivate_user(user_id=userId)
        if isinstance(deactivated, str):
            return user_error(message="User is already deactivated")

        if not deactivated:
            return server_error(message="An error occured while deactivating user")

        await submit_audit_record(
            route="admin/users/deactivate/userId",
            details=f"User {user.firstName} {user.lastName} deactivated user {userId} in lms",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to deactivate users in LMS")
        return server_error(
            message="Failed to deactivate users in LMS"
        )


@router.post(
    "/users/activate/{userId}",
    description="Route to activate user in system",
    response_model=activate.Output
)
async def activate_user_route(userId: str, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        activated = await activate_user(user_id=userId)
        if isinstance(activated, str):
            return user_error(message="User is already activated")

        if not activated:
            return server_error(message="An error occured while deactivating user")

        await submit_audit_record(
            route="admin/users/activate/userId",
            details=f"User {user.firstName} {user.lastName} activated user {userId} in lms",
            user_id=user.userId
        )
        return successful_response()

    except Exception:
        log.exception("Failed to activate users in LMS")
        return server_error(
            message="Failed to activate users in LMS"
        )


@router.post(
    "/users/update/{userId}",
    description="Route to update account",
    response_model=update.Output
)
async def update_user_route(userId: str, content: update.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        if not content.emailNotifications:
            content.emailNotifications = True

        if not content.textNotifications:
            content.textNotifications = False

        updated_user = {
            "first_name": content.firstName,
            "middle_name": content.middleName,
            "last_name": content.lastName,
            "suffix": content.suffix,
            "email": content.email,
            "phone_number": content.phoneNumber,
            "dob": datetime.datetime.strptime(content.dob, '%m/%d/%Y'),
            "eye_color": content.eyeColor,
            "height": (content.height.feet * 12 + content.height.inches) if content.height else None,
            "gender": content.gender,
            "photo_id": content.photoId,
            "other_id": content.otherId,
            "time_zone": content.timeZone,
            "modify_dtm": datetime.datetime.utcnow(),
            "text_notif": content.textNotifications,
            "email_notif": content.emailNotifications,
            "address": content.address,
            "city": content.city,
            "state": content.state,
            "zipcode": content.zipcode,
            "head_shot": content.headShot,
            "photo_id_photo": content.photoIdPhoto,
            "other_id_photo": content.otherIdPhoto
        }
        if content.password:
            updated_user.update(
                {"password": pbkdf2_sha256.hash(content.password)})

        updating = await update_user(user_id=userId, **updated_user)
        if not updating:
            return server_error(message="Something went wrong when updating the user")

        updated = await get_user(user_id=userId)
        updated = updated.dict()

        try:
            del updated["password"]
        except KeyError:
            pass
        # As of right now this is just returning True or false, will likely need to change to
        # return the actual user object after being updated

        await submit_audit_record(
            route="users/update/userId",
            details=f"User {user.firstName} {user.lastName} updated user {userId} with values {json.dumps(content.dict())}",
            user_id=user.userId
        )

        return successful_response(
            payload={
                "user": updated
            }
        )
    except Exception:
        log.exception("Failed to update user")
        return server_error(
            message="Failed to update user"
        )
