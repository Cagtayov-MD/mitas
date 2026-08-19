#!/bin/bash
cd /opt/mitas || exit 1
venvs/ocr/bin/python kurulum/27_kapanis_birlestir.py 2>&1 | tail -1
venvs/asr/bin/python kurulum/26_kapanis_pdf.py 2>&1 | tail -1
