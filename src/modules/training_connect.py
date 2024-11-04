import os
import asyncio
import re
import asyncio_redis
import json
import datetime
import tempfile
from pyppeteer.errors import TimeoutError
from pyppeteer import launch
from cuid2 import Cuid


from src import log
from src.utils.certificate_generation import generate_certificate_func
from src.utils.convert_date import convert_date
from src.modules.notifications import (
    certification_failed_users_notification,
    student_failed_users_notification,
    training_connect_failure_notification
)


def find_in_select(element: str, find: str):
    code = f'''() => {{
            const selectElement = document.querySelector("#{element}");
            const options = selectElement.options;
            const optionArray = [];
            for (let i = 0; i < options.length; i++) {{
                const option = options[i];
                optionArray.push({{
                    value: option.value,
                    text: option.text
                }});
            }}
            for (let i = 0; i < optionArray.length; i++) {{
                if (optionArray[i].text === `{find}`) {{
                    selectElement.value = optionArray[i].value;
                    break; // Exit the loop once a match is found
                }}
            }}
            }}'''
    return code


class TrainingConnect:
    def __init__(self):
        self.page = None
        self.browser = None
        self.redis = None

        self.logged_in = False
        self.match_user_url = ""
        self.email = ""
        self.users = []
        self.tmpfiles = []
        self.generated = []
        self.pattern = re.compile(r'(\d+)\s+(.+)')
        self.cuid_generator: Cuid = Cuid(length=15)

        self.queue_running = False
        self.queue_lock = asyncio.Lock()
        self.queue = []

    async def generate_cert(self, user, failed: bool):
        cert_id = user["certificate_id"] if user.get(
            "certificate_id") else self.cuid_generator.generate()
        try:
            issue_date = datetime.datetime.strptime(
                user['issue_date'].split(' ')[0], '%Y-%m-%d')
            expiry_date = datetime.datetime.strptime(
                user['expiry_date'].split(' ')[0], '%Y-%m-%d')

            cert = await generate_certificate_func(
                student_full_name=str(
                    user['first_name'] + " " + user['last_name']),
                instructor_full_name=str(user['instructor']),
                certificate_name=str(user['course_name']),
                completion_date=issue_date,
                expiration_date=expiry_date,
                certificate_number=str(cert_id),
                email=user.get('email'),
                phone_number=str(int(user['phone_number'])) if user.get(
                    'phone_number') else None
            )
            if not cert:
                return None

            if isinstance(cert, tuple):
                self.tmpfiles.append(
                    {"tempfile": cert[0], "failed": failed, "user": user})
            else:
                self.tmpfiles.append(
                    {"tempfile": cert, "failed": failed, "user": user})
            return cert
        except Exception as e:
            log.exception(
                "Something went wrong when trying to generate the users certificate.")
            training_connect_failure_notification(
                body="Failed to generate certificate", stack_trace=str(e))
            return None

    async def add_failed(self, failed_user, reason, upload_type):
        if upload_type == "certificate":
            cert = await self.generate_cert(failed_user, True)
            if isinstance(cert, tuple):
                reason = reason + f' {cert[1]}'
        self.users.append({
            "user": failed_user,
            "failed": True,
            "reason": reason
        })
        try:
            log.info(str(failed_user['first_name'] + " added to failed"))
        except Exception:
            pass

    async def create_student(self, user: dict, upload_type: str):
        try:

            if not user.get('phone_number'):
                await self.add_failed(user, "No phone number provided.", upload_type=upload_type)
                return

            if not user.get("height"):
                await self.add_failed(user, "No height provided.", upload_type=upload_type)
                return

            if not user.get("eye_color"):
                await self.add_failed(user, "No eye color provided.", upload_type=upload_type)
                return

            if not user.get("gender"):
                await self.add_failed(user, "No gender provided.", upload_type=upload_type)
                return

            if not user.get('house_number'):
                await self.add_failed(user, "House number not provided", upload_type=upload_type)
                return

            if not user.get('street_name'):
                await self.add_failed(user, "Street name not provided", upload_type=upload_type)
                return

            if not user.get('city'):
                await self.add_failed(user, "City not provided.", upload_type=upload_type)
                return

            if not user.get('state'):
                await self.add_failed(user, "State not provided.", upload_type=upload_type)
                return

            if not user.get('zipcode'):
                await self.add_failed(user, "Zip Code not provided.", upload_type=upload_type)
                return

            if not user.get('head_shot'):
                user['head_shot'] = 'default_headshot.jpg'

            try:
                user['dob'] = datetime.datetime.strptime(
                    user["dob"], '%Y-%m-%d %H:%M:%S')
                dob = user['dob'].strftime('%Y-%m-%d')
            except Exception:
                log.error(f"Failed to convert dob {user['dob']}")
                await self.add_failed(user, f"dob: {user['dob']}, incorrect format.", upload_type=upload_type)
                return

            await self.page.goto("https://dob-trainingconnect.cityofnewyork.us/Students/Create?providerId=36cd1e6e-62b5-4770-ad4f-08d97ed9594c")
            await self.page.waitForSelector('.col-auto')
            await self.page.type('#FirstName', str(user['first_name']))

            if user.get('middle_name'):
                await self.page.type('#MiddleName', str(user['middle_name']))

            await self.page.type('#LastName', str(user['last_name']))

            if user.get('suffix'):
                await self.page.type('#Suffix', str(user['suffix']))

            await self.page.evaluate(f'''() => {{
                    const dateInput = document.querySelector("#DateOfBirth");
                    dateInput.value = "{dob}";
                }}''', dob)

            fileInput = await self.page.querySelector('input[type=file]')
            await fileInput.uploadFile(f'./src/content/user/{user["head_shot"]}')

            await self.page.type('#AddressNumber', user['house_number'])
            await self.page.type('#AddressName', f"{user['street_name']} {user['apt_suite']}")
            await self.page.type('#City', user['city'])
            await self.page.type('#State-selectized', user['state'])
            # check to see if the course name box pops up, this means that the course exists, if its not visible it means the course doesnt exist
            is_visible = await self.page.evaluate(
                '''() => {
                    const element = document.querySelector('.selectize-dropdown.single.searchable');
                    const style = window.getComputedStyle(element);
                    return style.getPropertyValue('display') !== 'none';
                }'''
            )

            if not is_visible:
                log.error(
                    "failing this user because no state matched therefore address will not match")
                await self.add_failed(user, "An error occured while creating the user, please manually create.", upload_type=upload_type)
                return
            await self.page.keyboard.press('Enter')
            await self.page.type('#ZipCode', str(user['zipcode']))

            if user.get("email"):
                await self.page.type('#Email', str(user['email']))
            await self.page.type('#Phone', str(user['phone_number']))
            await self.page.evaluate(find_in_select("Height", str(user['height'])))
            await self.page.evaluate(find_in_select("Gender", str(user['gender'])))
            await self.page.evaluate(find_in_select("EyeColor", str(user['eye_color'])))

            # create the student
            await self.page.click('input[type="submit"]')

            # probably get the text of the dangers, which will say what is missing
            # and use it for errors in failed
            await self.page.waitFor(1000)

            try:
                dangers = await self.page.querySelectorAll(".text-danger.field-validation-error")
            except Exception:
                log.debug("No dangers found")
                dangers = None

            if dangers:
                log.debug(f"dangers found: {dangers}")
                # user not created
                await self.add_failed(user, "An error occured while creating the user, please manually create.", upload_type=upload_type)
            else:
                # user created
                log.info("student created")
        except Exception as e:
            log.exception("an exception occured while creating user")
            training_connect_failure_notification(
                body="Failed to create student", stack_trace=str(e))
            await self.add_failed(user, "An error occured while creating the user, please manually create.", upload_type=upload_type)

    async def add_certificate(self, user: dict, page_url: str, upload_type: str):
        try:
            log.debug("in add certificate function for " +
                      str(user['first_name']))
            # go to add certificate page for user
            await self.page.goto(page_url)
            await self.page.waitForSelector('a.btn.btn-primary')
            await self.page.click('a.btn.btn-primary')

            await self.page.waitForSelector('input[type=submit]')

            # converts dates from excel to be dates enterable into certificate date boxes
            issued_date = convert_date(user['issue_date']) if str.isnumeric(
                user['issue_date']) else user['issue_date']
            expiration_date = convert_date(user['expiry_date']) if str.isnumeric(
                user['expiry_date']) else user['expiry_date']

            issued_date = datetime.datetime.strptime(
                issued_date, "%Y-%m-%d %H:%M:%S")
            expiration_date = datetime.datetime.strptime(
                expiration_date, "%Y-%m-%d %H:%M:%S")
            issued_date = issued_date.strftime("%Y-%m-%d")
            expiration_date = expiration_date.strftime("%Y-%m-%d")

            course_name = str(user['course_name']).replace(
                "&amp;", "").replace("&nbsp;", "")

            await self.page.type('#CourseId-selectized', course_name)
            # check to see if the course name box pops up, this means that the course exists, if its not visible it means the course doesnt exist
            is_visible = await self.page.evaluate(
                '''() => {
                    const element = document.querySelector('.selectize-dropdown.single.searchable');
                    const style = window.getComputedStyle(element);
                    return style.getPropertyValue('display') !== 'none';
                }'''
            )

            if is_visible:
                cert = await self.generate_cert(user, False)
                if isinstance(cert, tuple):
                    self.users.append(
                        {"user": user, "failed": True, "reason": f'{cert[1]} Certificate was uploaded to Training Connect.'})
                    cert_file = cert[0]
                else:
                    cert_file = cert
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f_name = f.name
                    f.write(cert_file)

                await self.page.keyboard.press('Enter')
                await self.page.type('#CertificateNumber', str(user['certificate_id']).replace(" ", ""))
                await self.page.evaluate(f'''() => {{
                    const dateInput = document.querySelector("#IssuedDate");
                    dateInput.value = "{issued_date}";
                }}''', issued_date)
                await self.page.waitFor(500)
                await self.page.evaluate(f'''() => {{
                    const dateInput = document.querySelector("#ExpirationDate");
                    dateInput.value = "{expiration_date}";
                }}''', expiration_date)
                await self.page.type('#TrainerName', user['instructor'])

                fileInput = await self.page.querySelector('input[type=file]')

                await fileInput.uploadFile(f_name)
                await self.page.waitFor(500)

                await self.page.click('input[type=submit]')
                log.info(
                    f"Successfully added certificate for {str(user['first_name'])}")
                self.users.append({"user": user, "failed": False})
                os.remove(f_name)
            else:
                await self.add_failed(user, "Tried to add certificate for an incorrect course name.", upload_type=upload_type)
        except Exception as e:
            log.exception(
                "something went wrong when trying to add the users certificate")
            training_connect_failure_notification(
                body="Failed to add certificate to user", stack_trace=str(e))
            await self.add_failed(user, "An error occured while adding certificate, please manually upload.", upload_type=upload_type)

    async def goto_user_profile(self, user_profile_url):
        await self.page.goto(user_profile_url)

    async def add_to_course_provider(self, page_url):
        # go to users profile to start the updating of the user
        await self.goto_user_profile(page_url)
        await self.page.waitForSelector('input[type=submit]')

        # log.info("would attempt to click add to course provider now")
        # this will add the user to the course provider, disabled in case of testing
        await self.page.click('input[type=submit]')

    async def update_user(self, user: dict, page_url: str, upload_type: str):
        # go to users profile to start the updating of the user
        await self.goto_user_profile(page_url)

        # if the course provider button is there,
        # run the function add to course provider on the link the function returns and it will click to add the user
        course_provider_link = await self.page.evaluate('''() => {
                    const buttons = Array.from(document.querySelectorAll('a.h6.sc-link'));
                    return buttons.filter(button => button.textContent.includes('Add To Course Provider')).map(button => button.href)[0];
                }''')

        if course_provider_link:
            await self.add_to_course_provider(course_provider_link)

        # if the certificate id sent from the excel is not none, start adding the certificate
        await self.add_certificate(user, page_url, upload_type=upload_type)

        # resets the match user so it can proceed onto the next one freely, all runs asyncronously so it doesnt hit this til after
        # self.match_user_url = ""

    async def check_match(self, user, user_url, amount, index, upload_type: str):
        # visit users profile url to start validation
        await self.goto_user_profile(user_url)
        await self.page.waitForSelector(".sc-field-value", visible=True)
        await self.page.waitFor(1000)

        # this is what actually gets all the elements / field values which allows for us to get the values and check for matches
        fieldValuesElements = await self.page.querySelectorAll('.sc-field-value')

        fieldValues = []

        for fieldValueElement in fieldValuesElements:
            fieldValue = await self.page.evaluate('(element) => element.textContent', fieldValueElement)
            fieldValue = fieldValue.strip()
            fieldValues.append(fieldValue)

        # 5, 6, 7 are the phone, email and birthdate listed on a users profile, these are used to get the value of them
        # and then compare them to the actual users info below
        matchFieldValuesIndexes = {
            5: 'phone',
            6: 'email',
            7: 'birthDate'
        }

        matches = 0

        for fieldValueIndex, fieldValue in enumerate(fieldValues):
            if matches >= 2:
                break

            if fieldValueIndex in matchFieldValuesIndexes:
                matchFieldKey = matchFieldValuesIndexes[fieldValueIndex]
                # this will check if the fields above values are equal to the users
                if matchFieldKey == 'phone' and user.get('phone_number'):
                    phone = fieldValue.replace(
                        "-", "").replace(" ", "").replace("(", "").replace(")", "")
                    userPhone = int(
                        re.sub(r'\D', '', str(user['phone_number'])))

                    if str(phone) == str(userPhone):
                        matches += 1
                elif matchFieldKey == 'email' and user.get('email'):
                    email = fieldValue.lower()
                    userEmail = user['email'].lower()

                    if str(email) == str(userEmail):
                        matches += 1
                elif matchFieldKey == "birthDate" and user.get('date_of_birth'):
                    try:
                        birthDate = datetime.datetime.strptime(
                            fieldValue, "%m/%d/%Y")
                        birthDate = birthDate.strftime("%Y-%m-%d")

                        try:
                            userBirthDate = datetime.datetime.strptime(
                                user['date_of_birth'], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            userBirthDate = datetime.datetime.strptime(
                                user['date_of_birth'], "%m/%d/%Y")
                        userBirthDate = userBirthDate.strftime("%Y-%m-%d")

                        if str(birthDate) == str(userBirthDate):
                            matches += 1
                    except Exception as e:
                        log.exception("something when wrong")
                        training_connect_failure_notification(
                            body="Failed to check matches for student", stack_trace=str(e))
                        await self.add_failed(
                            failed_user=user,
                            reason="An error occured while adding certificate, please manually upload.",
                            upload_type=upload_type
                        )

        # currently functionality states if TWO matches are found on a users profile, attempt to update, otherwise
        # check if the amount of users found on STUDENT LOOKUP is equal to one, if so it only requires ONE match on the users profile
        if matches >= 2:
            self.match_user_url = self.page.url
            if upload_type == "certificate":
                await self.update_user(user, self.match_user_url, upload_type=upload_type)
            if upload_type == "student":
                await self.add_failed(user, "User already exists", upload_type=upload_type)
        elif amount == 1 and matches >= 1:
            self.match_user_url = self.page.url
            if upload_type == "certificate":
                await self.update_user(user, self.match_user_url, upload_type=upload_type)
            if upload_type == "student":
                await self.add_failed(user, "User already exists", upload_type=upload_type)
        else:
            if index == amount-1 and not self.match_user_url and upload_type == "certificate":
                log.error("not enough matches found on users profile")
                await self.add_failed(failed_user=user, reason="Could not match email, phone number or birthdate.", upload_type=upload_type)
            pass

        if index == amount and matches == 0 and upload_type == "student":
            # start creation of user here
            await self.create_student(user, upload_type=upload_type)

    async def do_lookup(self, user: dict, upload_type: str):
        if not user.get('first_name'):
            await self.add_failed(user, "No first name provided.", upload_type=upload_type)
            return

        if not user.get('last_name'):
            await self.add_failed(user, "No last name provided.", upload_type=upload_type)
            return

        log.debug("log 1: looking up " +
                  str(user['first_name'] + " " + user["last_name"]))

        if upload_type == 'student' or not user.get("osha_id") and not user.get("sstid") and not user.get("our_student"):
            if upload_type == 'student':
                log.debug("upload type is student")
            else:
                log.info(
                    "user has no sst or osha and is not tagged as 'our_student'")
            try:
                await self.page.goto(
                    "https://dob-trainingconnect.cityofnewyork.us/CourseProviders/StudentLookup/36cd1e6e-62b5-4770-ad4f-08d97ed9594c?type=StudentName"
                )

                await self.page.evaluate(
                    f"document.getElementById('StudentName').value = \"{user['first_name'].strip()} {user['last_name'].strip()}\""
                )
                await self.page.click("input[type='submit']")
                try:
                    await self.page.waitForSelector("a[role='button']", timeout=5000)

                    amountofUsers = int(await self.page.evaluate("document.querySelectorAll(`a[role='button']`).length"))

                    view_buttons = await self.page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll("a[role='button']"));
                        return buttons.filter(button => button.textContent.includes('View')).map(button => button.href).slice(0, 10);
                    }''')

                except Exception:
                    log.info("No users found")
                    amountofUsers = None

                if upload_type == 'student' and not amountofUsers:
                    log.info("creating student")
                    await self.create_student(user=user, upload_type=upload_type)
                    return

                elif amountofUsers and amountofUsers >= 10:
                    await self.add_failed(
                        failed_user=user,
                        reason="Skipped because there are too many users to check for matches.",
                        upload_type=upload_type
                    )

                elif amountofUsers:
                    for idx, userProfile in enumerate(view_buttons):
                        if not self.match_user_url:
                            await self.check_match(user, userProfile, amountofUsers, idx, upload_type)
                    self.match_user_url = ""

                else:
                    await self.add_failed(
                        failed_user=user,
                        reason="No users found when doing look up",
                        upload_type=upload_type
                    )

            except (KeyError, TimeoutError) as e:
                log.error(
                    "Selector element was not found on page meaning the user had zero results")
                reason = "An error occured while adding certificate, please manually upload."
                if upload_type == 'student':
                    reason = "An error occured while creating student, please manually upload."
                    training_connect_failure_notification(
                        body="Failed to create student", stack_trace=str(e))
                else:
                    training_connect_failure_notification(
                        body="Failed to upload certificate to student", stack_trace=str(e))

                await self.add_failed(
                    failed_user=user,
                    reason=reason,
                    upload_type=upload_type
                )
            return

        if user.get("sstid"):
            try:
                await self.page.goto(
                    "https://dob-trainingconnect.cityofnewyork.us/CourseProviders/StudentLookup/36cd1e6e-62b5-4770-ad4f-08d97ed9594c?type=CardId"
                )

                await self.page.evaluate(f"document.getElementById('CardId').value = \"{user['sstid']}\"")
                await self.page.click("input[type='submit']")
                await self.page.waitForSelector("a[role='button']", timeout=5000)

                url = await self.page.evaluate("document.querySelector(`a[role='button']`).href")

                await self.update_user(user, url, upload_type=upload_type)
            except (KeyError, TimeoutError):
                log.error(
                    "Selector element was not found on page meaning the user had zero results")
                await self.add_failed(
                    failed_user=user,
                    reason="An error occured while adding certificate, please manually upload.",
                    upload_type=upload_type
                )
            return

        if user.get("osha_id"):
            try:
                log.info("user has osha_id")
                await self.page.goto(
                    "https://dob-trainingconnect.cityofnewyork.us/CourseProviders/StudentLookup/36cd1e6e-62b5-4770-ad4f-08d97ed9594c?type=OshaId"
                )

                await self.page.evaluate(f"document.getElementById('OshaId').value = '{user['osha_id']}'")
                await self.page.click("input[type='submit']")
                await self.page.waitForSelector("a[role='button']", timeout=5000)

                url = await self.page.evaluate("document.querySelector(`a[role='button']`).href")

                await self.update_user(user, url, upload_type=upload_type)
            except (KeyError, TimeoutError):
                log.error(
                    "Selector element was not found on page meaning the user had zero results")
                await self.add_failed(
                    failed_user=user,
                    reason="An error occured while adding certificate, please manually upload.",
                    upload_type=upload_type
                )
            return

        if user.get("our_student"):
            try:
                await self.page.goto('https://dob-trainingconnect.cityofnewyork.us/CourseProviders/Dashboard/36cd1e6e-62b5-4770-ad4f-08d97ed9594c')
                await self.page.waitForSelector(".container.card", visible=True)

                await self.page.evaluate(
                    f"document.getElementById('Filter').value = \"{user['first_name'].strip()} {user['last_name'].strip()}\""
                )
                await self.page.click('button[type="submit"]')
                await self.page.waitForSelector("td.text-right", visible=True, timeout=5000)

                amountofUsers = int(await self.page.evaluate('document.querySelectorAll("td.text-right").length'))

                if 1 <= amountofUsers <= 10:
                    # go through each user and validate them here
                    view_buttons = await self.page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll('a.btn.btn-light'));
                        return buttons.filter(button => button.textContent.includes('View')).map(button => button.href);
                    }''')

                    for idx, userProfile in enumerate(view_buttons):
                        if not self.match_user_url:
                            await self.check_match(user, userProfile, amountofUsers, idx, upload_type)
                    self.match_user_url = ""
                elif amountofUsers > 10:
                    await self.add_failed(
                        failed_user=user,
                        reason="Skipped because there are too many users to check.",
                        upload_type=upload_type
                    )
                    log.info("added to failed array")
            except TimeoutError:
                log.error(
                    "Selector element was not found on page meaning the user had zero results")
                await self.add_failed(
                    failed_user=user,
                    reason="No user found in Training Connect.",
                    upload_type=upload_type
                )
            return

    async def run_queue_item(self, userJson: dict, retries: int = 1):

        try:
            upload_info = userJson['upload_info']
            upload_type = userJson['upload_info']['upload_type']
            try:
                log.debug(str(upload_info['position']) +
                          " " + str(upload_info['max']))

                if upload_info['position'] == 1:
                    self.email = upload_info['uploader']
                    try:

                        if not self.page and not self.logged_in:
                            log.info("starting browser and logging in...")

                            self.browser = await launch(
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

                            self.page = await self.browser.newPage()

                            await asyncio.gather(
                                self.login()
                            )
                    except Exception:
                        log.exception("THERE WAS AN ERROR, RELOGGING IN")

            except Exception as e:
                raise e
        except Exception as e:
            log.exception("Failed json loading user")
            training_connect_failure_notification(
                body="Failed to load user json", stack_trace=str(e))

        if userJson:
            try:
                await self.do_lookup(userJson, upload_type)
            except Exception as e:
                if retries >= 5:
                    log.exception(
                        "An exception occured while doing lookup final retry reached")
                    training_connect_failure_notification(
                        body="Final retry reached while doing lookup", stack_trace=str(e))
                    await self.add_failed(
                        failed_user=userJson,
                        reason="Unable to do lookup on user.",
                        upload_type=upload_type
                    )
                    return

                log.exception(
                    "An exception occured while doing lookup... retrying")
                if self.page:
                    await self.page.close()

                if self.browser:
                    await self.browser.close()

                self.page = None
                self.browser = None
                self.logged_in = False

                await self.run_queue_item(userJson, retries=retries+1)

        if upload_info['position'] == upload_info['max']:
            log.info("cleaning up for next queue...")

            failed_users = [user for user in self.users if user.get("failed")]
            if upload_type == 'certificate':
                failed_tmps = [tmp for tmp in self.tmpfiles if tmp['failed']]
                try:
                    certification_failed_users_notification(
                        self.email, failed_users, upload_info['max'], failed_tmps, upload_info["file_name"])
                except Exception as e:
                    log.exception(
                        "an error occured while sending failed notification")
                    training_connect_failure_notification(
                        body="Final retry reached while doing lookup", stack_trace=str(e))
            elif upload_type == "student":
                try:
                    student_failed_users_notification(
                        self.email, failed_users, upload_info.get("file_name"))
                except Exception as e:
                    log.exception(
                        "an error occured while sending failed notification")
                    training_connect_failure_notification(
                        body="An error occured while sending failed notification", stack_trace=str(e))

            self.email = ""
            self.match_user_url = ""

            self.users.clear()
            self.tmpfiles.clear()
            await self.page.close()
            await self.browser.close()
            self.page = None
            self.browser = None
            self.logged_in = False
        await asyncio.sleep(1)

    async def run_queue_task(self, uploads: str):
        if not uploads:
            return

        try:
            users = json.loads(uploads)
        except Exception:
            log.exception("Failed json loading users")

        for user_json in users:
            await self.run_queue_item(userJson=user_json)

    async def handle_queue(self):
        while True:
            if not self.queue_running:
                async with self.queue_lock:
                    if self.queue:
                        self.queue_running = True  # Update class attribute
                        uploads = self.queue.pop(0)
                        await self.run_queue_task(uploads)
                        self.queue_running = False  # Update class attribute
            await asyncio.sleep(1)  # Add this line to yield control

    async def start_queue(self):
        self.redis = await asyncio_redis.Connection.create(host=str(os.getenv("REDIS_HOST")), port=int(os.getenv("REDIS_PORT")))
        pubsub = await self.redis.start_subscribe()
        await pubsub.subscribe([os.getenv("TRAINING_CONNECT_QUEUE", 'training_connect_queue')])

        while True:
            message = await pubsub.next_published()
            user = message.value
            async with self.queue_lock:
                self.queue.append(user)

    async def login(self):
        # go to the sign in link
        await self.page.goto('https://dob-trainingconnect.cityofnewyork.us/Saml/InitiateSingleSignOn')
        try:
            await self.page.waitForSelector('input[name="username"]', visible=True, timeout=5000)
        except Exception:
            pass

        loggedIn = await self.page.querySelector('.alert.alert-success.alert-dismissible.fade.show')

        if not loggedIn:
            # after done waiting for username input to appear, enter information
            await self.page.type('input[name="username"]', os.getenv("TRAINING_CONNECT_EMAIL"))
            await self.page.type('input[name="password"]', os.getenv("TRAINING_CONNECT_PASSWORD"))
            await self.page.click('input[type="submit"]')

            # wait for logged in selector to be present and then validate if it says logged in,
            # if so start analyzation of users
            await self.page.waitForSelector('.alert.alert-success.alert-dismissible.fade.show', visible=True)
            result = await self.page.evaluate('document.body.innerText.includes("logged in")')

            if result:
                log.debug("logged in here")
                self.logged_in = True
            else:
                log.debug("not logged in")
                return None
        else:
            log.debug("already logged in")

    async def start_system(self):
        # launch the browser
        log.info("starting training connect....")

        await asyncio.gather(
            self.start_queue(),
            self.handle_queue()
        )
