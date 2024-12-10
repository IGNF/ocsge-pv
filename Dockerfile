FROM ubuntu:24.04
ARG TZ="Europe/Paris"
RUN ln -fs "/usr/share/zoneinfo/${TZ}" \
&& apt update \
&& DEBIAN_FRONTEND=noninteractive apt install -y tzdata \
&& dpkg-reconfigure --frontend noninteractive tzdata \
&& apt install -y python3 python3-pip python3-gdal
USER ubuntu
WORKDIR /home/ubuntu
COPY src app
COPY LICENCE.md LICENCE.md
COPY LICENSE.md LICENSE.md
RUN python3 -m pip install pip \
&& python3 -m pip install -r ./scripts/requirements.txt

CMD ["bash"]