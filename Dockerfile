FROM python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-enchant

WORKDIR /bot

COPY requirements.txt /bot/
RUN pip install -r requirements.txt

COPY . /bot

CMD python dejavu_bot.py
