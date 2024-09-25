# 使用pytorch的特定版本作为基础镜像
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

WORKDIR /code

COPY . /code

RUN pip install docker

# pip换源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 在容器中安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 -y

RUN apt-get -y install vim

CMD ["python", "main.py"]