# syntax=docker/dockerfile:1
FROM python:3.12-alpine
 
USER 1000:1000

RUN mkdir -p /opt/netbox-zabbix
COPY --chown=1000:1000 . /opt/netbox-zabbix
WORKDIR /opt/netbox-zabbix
RUN if ! [ -f ./config.py ]; then cp ./config.py.example ./config.py; fi
RUN pip install -r ./requirements.txt
ENTRYPOINT ["python"]
CMD ["/opt/netbox-zabbix/netbox_zabbix_sync.py", "-v"]
