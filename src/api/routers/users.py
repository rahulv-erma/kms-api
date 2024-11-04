from passlib.hash import pbkdf2_sha256
from fastapi import APIRouter, Depends, Request, UploadFile, File, Response, Form
from fastapi.responses import FileResponse
import uuid
import datetime
from typing import Union, List
from io import BytesIO

from src import log, img_handler
from src.api.api_models import global_models, pagination
from src.utils.image import is_valid_image, resize_image
from src.api.api_models.users import (
    me,
    register,
    logout,
    login,
    forgot,
    my_certifications,
    my_courses,
    my_schedule,
    lookup,
    update,
    upload,
    list_certificates,
    load_certificate,
    role
)
from src.api.lib.base_responses import successful_response, user_error, server_error
from src.api.lib.auth.auth import AuthClient
from src.database.sql.user_functions import (
    get_user,
    create_user,
    update_user,
    get_user_class,
    get_user_courses,
    get_user_type,
    get_user_roles,
    manage_user_roles,
    get_user_certifications,
    upload_user_pictures,
    get_certificates
)
from src.database.sql.audit_log_functions import submit_audit_record
from src.database.sql.course_functions import get_schedule
from src.utils.session import get_session, create_session, delete_session
from src.modules.forgot_password import create_reset, read_jwt, get_reset, remove_reset
from src.utils.camelCase import camelCase
from src.utils.roles import roles as db_roles
from src.modules.save_content import save_content
from src.modules.notifications import self_register_notification, user_register_notification, password_reset_notification

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Details not found"}}
)


@router.post(
    "/login",
    description="Route to login",
    response_model=login.Output
)
async def login_route(content: login.Input):
    try:
        if not content.email or not content.password:
            return user_error(
                message="Email and password must be provided"
            )

        user = await get_user(email=content.email)
        if not user:
            return user_error(
                message="User does not exist with this email"
            )

        if not user.active:
            return user_error(message="Account no longer active, please contact administrator.")

        if not pbkdf2_sha256.verify(content.password, user.password):
            return user_error(
                message="Password does not match"
            )

        sessionId = create_session(user.userId)

        user.password = None
        # set image handler for allowing image viewing
        img_handler.set_key(key=user.userId, token=sessionId, ex=259200)
        return successful_response(
            payload={
                "user": user.dict(),
                "sessionId": sessionId,
                "roles": await get_user_roles(user.userId)
            }
        )
    except Exception:
        log.exception(
            f"An error occured while logging in user {content.email}")
        return server_error(
            message="Failed to login user"
        )


@router.post(
    "/register",
    description="Route to register",
    response_model=register.Output,
    response_model_exclude_unset=True
)
async def register_route(content: register.Input):
    user_id = str(uuid.uuid4())
    try:

        # Check if user exists
        if await get_user(email=content.email):
            return user_error(
                message="Email address already exists"
            )

        if not content.emailNotifications:
            content.emailNotifications = True

        if not content.textNotifications:
            content.textNotifications = False

        newUser = {
            "user_id": user_id,
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
            "head_shot": None,
            "photo_id": None,
            "other_id": None,
            "photo_id_photo": None,
            "other_id_photo": None,
            "password": pbkdf2_sha256.hash(content.password),
            "time_zone": content.timeZone,
            "create_dtm": datetime.datetime.utcnow(),
            "modify_dtm": datetime.datetime.utcnow(),
            "active": True,
            "text_notif": content.textNotifications,
            "email_notif": content.emailNotifications,
            "expiration_date": None,
            "address": content.address,
            "city": content.city,
            "state": content.state,
            "zipcode": content.zipcode
        }

        created_user = await create_user(newUser=newUser)
        if isinstance(created_user, str):
            return user_error(
                message=f"{created_user} is already taken"
            )

        if not created_user:
            raise SystemError("Failed to create user")

        sessionId = create_session(user_id=newUser["user_id"])
        newUser["height"] = content.height.dict()
        newUser["dob"] = str(newUser["dob"])
        newUser["create_dtm"] = str(newUser["create_dtm"])
        newUser["modify_dtm"] = str(newUser["modify_dtm"])
        user = global_models.User(**camelCase(newUser))
        user.textNotifications = content.textNotifications
        user.emailNotifications = content.emailNotifications

        if not await manage_user_roles(roles=['student'], user_id=user_id, action="add"):
            return server_error(
                message="Failed to assign roles to user"
            )
        user.password = content.password
        self_register_notification(user)
        user.password = None
        # set image handler for allowing image viewing
        img_handler.set_key(key=user.userId, token=sessionId, ex=259200)
        return successful_response(
            payload={
                "user": user.dict(),
                "roles": await get_user_roles(user_id),
                "sessionId": sessionId
            }
        )

    except Exception:
        log.exception("An error occured while creating a user")
        return server_error(
            message="Failed to create user"
        )


@router.post(
    "/logout",
    description="Route to logout",
    response_model=logout.Output
)
async def logout_route(request: Request, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        sessionId = request.headers.get("authorization")
        if not sessionId:
            return user_error(
                message="No Authorization header present"
            )

        session = get_session(sessionId.replace("Bearer ", ""))

        if not session:
            return user_error(
                message="No session found"
            )

        delete_session(session)
        # delete image handler for allowing image viewing
        img_handler.delete_key(redis_key=user.userId)
        return successful_response()
    except Exception:
        log.exception(
            f"An error occured while logging out session {sessionId}")
        return server_error(
            message="Failed to log out user"
        )


@router.get(
    "/me",
    description="Route to get logged in user info",
    response_model=me.Output
)
async def me_route(request: Request, user: global_models.User = Depends(AuthClient(use_auth=True))):
    try:
        if not user.userId:
            return server_error(
                message="No session found"
            )

        user = await get_user(user_id=user.userId)
        if not user:
            return user_error(
                message="No user found for that session"
            )

        user_roles = await get_user_roles(user_id=user.userId)
        user.password = None

        token = request.headers.get('Authorization')
        if token:
            try:
                token = token.replace('Bearer ', '')
                img_handler.set_key(key=user.userId, token=token, ex=259200)
            except Exception:
                log.exception("Failed to set new image handler key")

        return successful_response(
            payload={
                "user": user.dict(),
                "roles": user_roles
            }
        )
    except Exception:
        log.exception(
            f"An error occured while getting user data for {user.userId}")
        return server_error(
            message="Failed to get user data"
        )


@router.get(
    "/profile/{userId}",
    description="Route to get a users profile",
    response_model=me.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def users_profile(userId: str):
    try:
        user = await get_user(user_id=userId)
        if not user:
            return server_error(
                message="No user found for that session"
            )

        user_roles = await get_user_roles(user_id=user.userId)
        user.password = None

        return successful_response(
            payload={
                "user": user.dict(),
                "roles": user_roles
            }
        )
    except Exception:
        log.exception(
            f"An error occured while getting user profile for {userId}")
        return server_error(
            message="Failed to get user data"
        )


@router.post(
    "/lookup/{roleName}",
    description="Route look up users based off of role",
    response_model=lookup.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def user_lookup(roleName: str, user: lookup.Input, page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        if roleName not in db_roles:
            return user_error(
                message='Unknown role name'
            )
        users, total_pages = await get_user_type(user=user, roleName=roleName, page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "users": users,
                "pagination": pg.dict()
            }
        )
    except Exception:
        log.exception(f"Failed to get {roleName}")
        return server_error(
            message=f"Failed to get {roleName}"
        )


# TODO: this needs a model
# TODO: need to test
@router.post(
    "/forgot-password",
    description="Sample Endpoint",
    response_model=forgot.Output
)
async def forgot_password(content: forgot.Input):
    try:
        if not content:
            return user_error(message="Content must be provided")

        user = await get_user(email=content.email)

        if not user:
            return user_error(
                message="User does not exist with this email"
            )

        create_reset(content.email, user.userId, 600)

        try:
            code = get_reset(content.email)

            if not code:
                return user_error(message="Something went wrong when trying to get a reset code")

            password_reset_notification(user, code)
        except Exception:
            log.exception(
                f"An error occured while sending an email to {content.email}")
            return server_error(
                message="Failed to send email to user"
            )

        return successful_response()
    except Exception:
        log.exception(
            f"An error occured while sending a forgot password for user {user.userId}")
        return server_error(
            message="Failed to send password reset"
        )


# TODO: need to test
@router.post(
    "/forgot-password/{token}",
    description="Sample Endpoint",
    response_model=forgot.Output
)
async def forgot_password_jwt(token: str, content: forgot.Input2):
    email = read_jwt(token)
    if not email or not email['email']:
        log.exception("JWT is not set or has nothing inside of it", email)
        return server_error(message="Something went wrong")

    if not content.newPassword:
        return user_error(message="Must be given a new password")

    newPass = pbkdf2_sha256.hash(content.newPassword)

    if not newPass:
        log.exception("Something went wrong when trying to hash the password")
        return server_error(message="Something went wrong")

    if not get_reset(email['email']):
        return user_error(message="No reset code found")

    try:
        user = await get_user(email=email['email'])
        await update_user(user_id=user.userId, password=newPass)
        remove_reset(email['email'])
        return successful_response()
    except Exception:
        log.exception(
            "Something went wrong when trying to update the users password")
        return server_error(message="Failed to update user")


@router.get(
    "/my-certificates",
    description="Route to get the users own certificates",
    response_model=my_certifications.Output
)
async def my_certifications_route(user: global_models.User = Depends(AuthClient(use_auth=True)), page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        certifications, total_pages = await get_user_certifications(user_id=user.userId, page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "certificates": certifications,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception(
            f"Failed to get list of certifications for userId {user.userId}")
        return server_error(
            message="Failed to get certifications for user"
        )


@router.get(
    "/certificates/list",
    description="Route to get load user certificates",
    response_model=list_certificates.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def certificate_list_route(page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        certifications, total_pages = await get_certificates(page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "certificates": certifications,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception("Failed to get user certificates")
        return server_error(message="Failed to get user certificates")


@router.get(
    "/certificates/load/{userId}/{certificateNumber}",
    description="Route to load a specific users specific certificate",
    response_model=load_certificate.Output,
    response_model_exclude_unset=True,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def load_user_certificate_route(userId: str, certificateNumber: str):
    try:
        certifications, _ = await get_user_certifications(user_id=userId, certificate_number=certificateNumber)
        if not certifications:
            return server_error(message="Failed to get certificates")

        return successful_response(
            payload={
                "certificate": certifications[0]
            }
        )

    except Exception:
        log.exception("Failed to get certifications")
        return server_error(
            message="Failed to get certificates"
        )


@router.get(
    "/certificates/{userId}",
    description="Route to get another users certificates",
    response_model=my_certifications.Output
)
async def get_certificates_by_userid(
    userId: str,
    user: global_models.User = Depends(AuthClient(use_auth=True)),
    page: int = None,
    pageSize: int = None
):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        certifications, total_pages = await get_user_certifications(user_id=userId, page=page, pageSize=pageSize)

        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )

        return successful_response(
            payload={
                "certificates": certifications,
                "pagination": pg.dict()
            }
        )

    except Exception:
        log.exception(
            f"Failed to get list of certifications for userId {user.userId}")
        return server_error(
            message="Failed to get certifications for user"
        )


@router.get(
    "/my-courses",
    description="Route to get 'my' courses",
    response_model=my_courses.Output
)
async def my_courses_route(
    complete: bool = False,
    user: global_models.User = Depends(AuthClient(use_auth=True)),
    page: int = None,
    pageSize: int = None
):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        courses, total_pages = await get_user_courses(user_id=user.userId, complete=complete, page=page, pageSize=pageSize)

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
        log.exception(
            f"Failed to get list of courses for userId {user.userId}")
        return server_error(
            message="Failed to get courses for user"
        )


@router.post(
    "/update/me",
    description="Route to update self account",
    response_model=update.Output
)
async def update_me_route(content: update.Input, user: global_models.User = Depends(AuthClient(use_auth=True))):
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
            "other_id": content.photoId,
            "time_zone": content.timeZone,
            "create_dtm": datetime.datetime.utcnow(),
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

        updating = await update_user(user_id=user.userId, **updated_user)
        if not updating:
            return server_error(message="Something went wrong when updating the user")

        updated = await get_user(user_id=user.userId)
        updated = updated.dict()

        try:
            del updated["password"]
        except KeyError:
            pass
        # As of right now this is just returning True or false, will likely need to change to
        # return the actual user object after being updated
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


@router.get(
    "/courses/{userId}",
    description="Route to get a users courses",
    response_model=my_courses.Output
)
async def courses_by_userid(
    userId: str,
    complete: bool = False,
    user: global_models.User = Depends(AuthClient(use_auth=True)),
    page: int = None,
    pageSize: int = None
):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        courses, total_pages = await get_user_courses(user_id=userId, complete=complete, page=page, pageSize=pageSize)

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
        log.exception(
            f"Failed to get list of courses for userId {user.userId}")
        return server_error(
            message="Failed to get courses for user"
        )


@router.get(
    "/my-schedule",
    description="Route to get a users course schedule",
    response_model=my_schedule.Output
)
async def my_schedule_route(user: global_models.User = Depends(AuthClient(use_auth=True)), page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        schedule, total_pages = await get_schedule(user_id=user.userId, page=page, pageSize=pageSize)
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
        log.exception(f"Failed to load schedule for user {user.userId}")
        return server_error(
            message="Failed to get schedule"
        )


@router.get(
    "/schedule/{userId}",
    description="Route to get a users course schedule",
    response_model=my_schedule.Output
)
async def user_schedule_route(userId: str, user: global_models.User = Depends(AuthClient(use_auth=True)), page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        schedule, total_pages = await get_schedule(user_id=userId, page=page, pageSize=pageSize)
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
        log.exception(f"Failed to load schedule for user {userId}")
        return server_error(
            message="Failed to get schedule"
        )


@router.get(
    "/{roleName}",
    description="Route to get all users by role",
    response_model=role.Output,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def roleName_route(roleName: str, page: int = None, pageSize: int = None):
    if isinstance(page, int) and page <= 0:
        page = 1
    try:
        if roleName not in db_roles:
            return user_error(
                message="Role does not exist"
            )
        users, total_pages = await get_user_class(role=roleName, page=page, pageSize=pageSize)
        pg = pagination.PaginationOutput(
            curPage=page,
            totalPages=total_pages,
            pageSize=pageSize
        )
        return successful_response(
            payload={
                "users": users,
                "pagination": pg.dict()
            }
        )
    except Exception:
        log.exception(f"Failed to get {roleName}")
        return server_error(
            message=f"Failed to get {roleName}"
        )


@router.get(
    "/content/load/{fileId}",
    description="Route to load content"
)
async def load_content(fileId: str, uid: str, size: int = 1024):
    try:
        if not img_handler.get_key(redis_key=uid):
            return user_error(
                status_code=403,
                message="Unauthorized"
            )
        fileLocation = rf"./src/content/users/{fileId}"

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
        log.exception(
            "Something went wrong when trying to retrive the image for a course")
        return server_error(message="Something went wrong when retrieving the image.")


@router.post(
    "/register/{role}",
    description="Route to register a role type",
    response_model=register.Output,
    response_model_exclude_unset=True
)
async def register_role_route(role: str = None, content: register.Input = None, user: global_models.User = Depends(AuthClient(use_auth=True))):
    if not role:
        return user_error(message="Must supply a role")

    user_id = str(uuid.uuid4())
    try:

        user_roles = await get_user_roles(user.userId)
        if not user_roles:
            return user_error(message="User requesting doesnt have any roles")

        roles = []
        for name in user_roles:
            roles.append(name['roleName'])

        if 'superuser' not in roles and role in ['admin', 'superuser']:
            return user_error(message=f"Cannot make an account for {role} with these roles ['roles']")

        # Check if user exists
        if await get_user(email=content.email):
            return user_error(
                message="Email address already exists"
            )

        if not content.emailNotifications:
            content.emailNotifications = True

        if not content.textNotifications:
            content.textNotifications = False

        newUser = {
            "user_id": user_id,
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
            "head_shot": None,
            "photo_id": None,
            "other_id": None,
            "photo_id_photo": None,
            "other_id_photo": None,
            "password": pbkdf2_sha256.hash(content.password),
            "time_zone": content.timeZone,
            "create_dtm": datetime.datetime.utcnow(),
            "modify_dtm": datetime.datetime.utcnow(),
            "active": True,
            "text_notif": content.textNotifications,
            "email_notif": content.emailNotifications,
            "expiration_date": None,
            "address": content.address,
            "city": content.city,
            "state": content.state,
            "zipcode": content.zipcode
        }

        created_user = await create_user(newUser=newUser)
        if isinstance(created_user, str):
            return user_error(
                message=f"{created_user} is already taken"
            )

        if not created_user:
            raise SystemError("Failed to create user")

        if not await manage_user_roles(roles=[role], user_id=user_id, action="add"):
            return server_error(
                message="Failed to assign roles to user"
            )

        newUser["height"] = content.height.dict()
        newUser["dob"] = str(newUser["dob"])
        newUser["create_dtm"] = str(newUser["create_dtm"])
        newUser["modify_dtm"] = str(newUser["modify_dtm"])
        user = global_models.User(**camelCase(newUser))
        user.password = content.password
        user_register_notification(user)

        await submit_audit_record(
            route=f"users/register/{role}",
            details=f"User {user.firstName} {user.lastName} registered email {content.email} to LMS",
            user_id=user.userId
        )
        return successful_response(
            payload={
                "userId": user_id
            }
        )

    except Exception:
        log.exception(
            f"An error occured while creating user account for {role}")
        return server_error(
            message=f"An error occured while creating user account for {role}"
        )


@router.post(
    "/upload/content/{userId}",
    description="Route to upload a user pictures",
    response_model=upload.Output,
    response_model_exclude_unset=True,
)
async def upload_user_picture_route(
    userId: str,
    headShot: Union[UploadFile, None] = File(None),
    photoIdPhoto: Union[UploadFile, None] = File(None),
    otherIdPhoto: Union[UploadFile, None] = File(None),
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        submit_to_db = {}
        if headShot:
            saved = await save_content(
                types="users",
                file=headShot,
                content_types=['image/png', 'image/jpeg', 'image/jpg']
            )
            if not saved["success"]:
                return user_error(
                    message=saved["reason"]
                )
            submit_to_db["head_shot"] = saved["file_id"]

        if photoIdPhoto:
            saved = await save_content(
                types="users",
                file=photoIdPhoto,
                content_types=['image/png', 'image/jpeg', 'image/jpg']
            )
            if not saved["success"]:
                return user_error(
                    message=saved["reason"]
                )
            submit_to_db["photo_id_photo"] = saved["file_id"]

        if otherIdPhoto:
            saved = await save_content(
                types="users",
                file=otherIdPhoto,
                content_types=['image/png', 'image/jpeg', 'image/jpg']
            )
            if not saved["success"]:
                return user_error(
                    message=saved["reason"]
                )
            submit_to_db["other_id_photo"] = saved["file_id"]

        saved_photos = await upload_user_pictures(
            save_to_db=submit_to_db,
            user_id=userId,
            user=user
        )
        if not saved_photos:
            return server_error(message="Failed to upload files")

        return successful_response(
            payload=camelCase(submit_to_db)
        )
    except Exception:
        log.exception("Failed to add pictures to user")
        return server_error(
            message="Failed to add pictures to user"
        )


@router.post(
    "/upload/bulk/headshots",
    description="Route to upload bulk users headshots",
    response_model=upload.BulkOutput,
    response_model_exclude_unset=True,
    dependencies=[Depends(AuthClient(use_auth=True))]
)
async def upload_bulk_headshot_route(
    userIds: List[str] = Form(...),
    pictures: List[UploadFile] = File(...),
    user: global_models.User = Depends(AuthClient(use_auth=True))
):
    try:
        submit_to_db = {}
        uploaded = []
        zipped = list(zip(userIds, pictures))
        for picture in zipped:
            saved = await save_content(
                types="users",
                file=picture[1],
                content_types=['image/png', 'image/jpeg', 'image/jpg']
            )
            if not saved["success"]:
                uploaded.append(
                    {"failed": True, "reason": saved["reason"], "userId": picture[0], "headShot": None})

            submit_to_db["head_shot"] = saved["file_id"]

            saved_photos = await upload_user_pictures(
                save_to_db=submit_to_db,
                user_id=picture[0],
                user=user
            )
            if not saved_photos:
                uploaded.append(
                    {"failed": True, "reason": "Failed to upload headshot", "userId": picture[0], "headShot": None})

            uploaded.append({
                "failed": False,
                "userId": picture[0],
                "headShot": saved["file_id"]
            })

        return successful_response(
            payload={
                "headShots": uploaded
            }
        )

    except Exception:
        log.exception("Failed to add pictures to users")
        return server_error(
            message="Failed to add pictures to users"
        )
