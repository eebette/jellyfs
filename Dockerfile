FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends fuse3 \
 && rm -rf /var/lib/apt/lists/* \
 && echo "user_allow_other" >> /etc/fuse.conf

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/jellyfs ./jellyfs

ENTRYPOINT ["python", "-m", "jellyfs"]
CMD ["/media/source", "/media/mount", "-f", "--allow-other"]
