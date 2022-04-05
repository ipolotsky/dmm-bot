FROM python:3.9
WORKDIR /opt
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY . .
ENTRYPOINT ["python3", "main.py"]