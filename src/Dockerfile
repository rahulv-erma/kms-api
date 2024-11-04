# FROM python:3.10-alpine
FROM python:3.8.9

RUN apt-get update && apt-get install -y cron
ENV PYTHONUNBUFFERED=1

WORKDIR /source

# RUN pip install git+https://github.com/doitsolutions/SQL_ORM.git

ADD . /source/src/

RUN mv /source/src/class_reminders.py /source/

RUN pip install --upgrade pip

RUN pip install -r /source/src/requirements.txt

# Pyppeteer
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    --no-install-recommends \
    && curl -sSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    --no-install-recommends

# It won't run from the root user.
RUN groupadd chrome && useradd -g chrome -s /bin/bash -G audio,video chrome \
    && mkdir -p /home/chrome && chown -R chrome:chrome /home/chrome

# move cron file to the proper place
RUN mv /source/src/cronjob.cron /etc/cron.d/cronjob.cron

# Give the cron file the correct permissions
RUN chmod 0644 /etc/cron.d/cronjob.cron

# Apply cron job
RUN crontab /etc/cron.d/cronjob.cron
RUN touch /var/log/cron.log

# set timezone to eastern standard
RUN rm -rf /etc/localtime
RUN ln -s /usr/share/zoneinfo/America/New_York /etc/localtime

# Run the app
CMD printenv > /etc/environment && cron && uvicorn src.api.app:app --host 0.0.0.0 --port 8080
