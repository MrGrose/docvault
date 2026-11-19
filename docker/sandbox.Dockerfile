FROM python:3.12-slim
WORKDIR /work
COPY src/sandbox /opt/sandbox
RUN useradd -u 1000 -m sandbox
USER sandbox
ENV PYTHONPATH=/opt
CMD ["python", "/work/task.py"]