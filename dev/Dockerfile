FROM python:3.10

RUN apt-get update && apt-get install -y openssh-server &&\
    echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config &&\
    mkdir /var/run/sshd &&\
    echo 'root:password' | chpasswd

EXPOSE 22

CMD [ "/usr/sbin/sshd", "-D" ]
