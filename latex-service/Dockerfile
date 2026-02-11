FROM python:3.14-slim

# Install TeX Live and curl (for healthcheck). No build-essential needed
# since we removed xhtml2pdf/pycairo.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        texlive-latex-recommended \
        texlive-fonts-recommended \
        texlive-latex-extra \
        texlive-fonts-extra \
        lmodern \
        cm-super \
        latexmk && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
