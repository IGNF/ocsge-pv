FROM ubuntu:24.04
ARG TZ="Europe/Paris"
ARG HOST_UID=1001
ARG HOST_GID=1001
RUN ln -fs "/usr/share/zoneinfo/${TZ}" \
&& apt update \
&& apt -y upgrade \
&& DEBIAN_FRONTEND=noninteractive apt -y install tzdata \
&& dpkg-reconfigure --frontend noninteractive tzdata \
&& groupadd -g $HOST_GID usergroup \
&& useradd -m -u $HOST_UID -g usergroup -G usergroup user -d /home/user \
&& apt -y install python3 python3-gdal libgdal-dev python3-venv python3-pip git postgresql postgis gdal-bin jq \
&& apt -y autoremove --purge \
&& apt -y clean
COPY . /app
WORKDIR /app
RUN chown -R user:usergroup /app
USER user
ENV OCSGE_PV_FIXTURE_DIR="/app/tests/fixtures"
ENV OCSGE_PV_RESOURCE_DIR="/app/src/ocsge_pv/resources"
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN . /app/venv/bin/activate
RUN python3 -m pip install "gdal==$(gdal-config --version)"
RUN python3 -m pip install .[dev]
RUN python3 -m pip install .[test]
RUN python3 -m pip install .[doc]
RUN python3 -m pip install -e .
RUN pre-commit install

CMD ["python3", "-m", "pytest"]
