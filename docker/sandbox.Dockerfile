FROM python:3.12-slim
WORKDIR /work
COPY src/sandbox/sdk_client.py /usr/local/lib/python3.12/site-packages/sandbox_sdk_client.py
RUN useradd -u 1000 -m sandbox
USER sandbox
ENV PYTHONPATH=/work
CMD ["python", "/work/task.py"]