FROM python:3.12-slim

WORKDIR /srv

COPY sed_reporting/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY reporting /srv/reporting
COPY sed_reporting /srv/sed_reporting
COPY sed_report_engine /srv/sed_report_engine

ENV PYTHONPATH=/srv
EXPOSE 8010

CMD ["python", "-m", "uvicorn", "sed_report_engine.app:app", "--host", "0.0.0.0", "--port", "8010"]
