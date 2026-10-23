FROM python:3.12-slim

WORKDIR /srv

# Built from the sed workspace (docker compose) or from this repo on Render
# after vendor/reporting and vendor/sed_reporting are present.
COPY sed_report_engine/requirements-prod.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY reporting /srv/reporting
COPY sed_reporting /srv/sed_reporting
COPY sed_report_engine /srv/sed_report_engine

ENV PYTHONPATH=/srv
EXPOSE 8010

CMD ["sh", "/srv/sed_report_engine/start.sh"]
